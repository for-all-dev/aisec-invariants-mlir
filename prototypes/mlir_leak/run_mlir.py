"""
Differential non-interference across MLIR lowering pipelines.

The ctbench experiment with the "compiler axis" swapped from (gcc/clang x flags)
to (MLIR lowering-pipeline variants). For each source-oblivious core-MLIR kernel
we lower it through several `mlir-opt` pipelines (LLVM backend fixed via --opt),
link each into the Valgrind-gated `mlir_driver.c`, and run the leak_check
differential test (class A vs class B secret). A `.`->`L` flip on a
source-oblivious kernel = a lowering-introduced leak.

    python3 run_mlir.py                                  # matvec,cond,select,gather x P0..P5
    python3 run_mlir.py --pipelines P0 --opt O3          # LLVM backend axis
    python3 run_mlir.py --kernels idx_gather --pipelines P0 P3

Reuses leak_check/instruments.py for the callgrind COUNT channel, and reuses
leak_check/noninterference.py's context-varying floor+stability method (via
leak_check/differential.py) for the COUNT-hygiene decision, instead of a
fixed-path interleaved sample. The TAINT channel is parsed locally (below)
with a broadened pattern: instruments.memcheck_taint only matches the
control-flow message ("... depends on uninitialised value"), but an ADDRESS leak
(e.g. gather) prints "Use of uninitialised value of size N" -- so we classify
both here. Taint is primary; counts corroborate.

NOTE: this used to import `_disjoint` from noninterference.py and compare
interleaved counts sampled at a FIXED secret path. `_disjoint` was removed by
noninterference.py's own floor/stability rewrite (commit d0d3232, "the count
channel is confounded by measurement context") -- every run of this file
since then raised ImportError, and a fixed-path sample is exactly the
confound that rewrite exists to catch (valgrind disables ASLR, so two secret
classes at the same fixed path can differ only by what's baked into the
path/layout, not just the secret). Fixed here by reusing the context-varying
method directly instead of re-deriving a weaker one.
"""
import argparse
import array
import os
import random
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "leak_check")))
import differential as D
import instruments as I
import noninterference as NI

BUILD = os.path.join(HERE, "build")
SEC = os.path.join(HERE, "secrets")
MLIR_OPT, MLIR_TRANSLATE, CLANG = "mlir-opt-18", "mlir-translate-18", "clang-18"

# Bare-pointer memref calling convention; reconcile-unrealized-casts must be last.
TAIL = ("--convert-index-to-llvm --convert-cf-to-llvm --convert-arith-to-llvm "
        "--finalize-memref-to-llvm "
        "--convert-func-to-llvm=use-bare-ptr-memref-call-conv=1 "
        "--reconcile-unrealized-casts")

# The compiler axis: MLIR lowering pipelines (LLVM backend held fixed, see --opt).
# Values are token LISTS (P4's one-shot-bufferize option contains a space, so it
# must stay a single token -- a space-split string would break it).
PIPELINES = {
    "P0": ["--convert-linalg-to-loops", "--convert-scf-to-cf", "--expand-strided-metadata"],
    "P1": ["--convert-linalg-to-affine-loops", "--lower-affine", "--convert-scf-to-cf", "--expand-strided-metadata"],
    "P2": ["--canonicalize", "--cse", "--convert-linalg-to-loops", "--convert-scf-to-cf", "--expand-strided-metadata"],
    "P3": ["--convert-linalg-to-affine-loops", "--affine-super-vectorize", "--lower-affine",
           "--convert-scf-to-cf", "--convert-vector-to-scf", "--expand-strided-metadata", "--convert-vector-to-llvm"],
    # P4: one-shot bufferization (tensor-source kernels only). buffer-results-to-out-params
    # gives the (inputs..., out) bare-ptr ABI the driver expects.
    "P4": ["--eliminate-empty-tensors", "--empty-tensor-to-alloc-tensor",
           "--one-shot-bufferize=bufferize-function-boundaries=1 function-boundary-type-conversion=identity-layout-map",
           "--buffer-results-to-out-params", "--buffer-deallocation-pipeline",
           "--convert-linalg-to-loops", "--convert-scf-to-cf", "--expand-strided-metadata"],
    "P5": ["--linalg-generalize-named-ops", "--convert-linalg-to-loops", "--convert-scf-to-cf", "--expand-strided-metadata"],
}


def _wf(path, vals, typ):
    array.array(typ, vals).tofile(open(path, "wb"))


# Each kernel: source .mlir + the two secret classes A/B (identical size).
_R = random.Random(0)
KERNELS = {
    "matvec": {"src": "matvec.mlir", "gen": lambda: (
        _wf(f"{SEC}/matvec_A.bin", [0.0] * (256 * 256), "f"),
        _wf(f"{SEC}/matvec_B.bin", [_R.gauss(0, 1) for _ in range(256 * 256)], "f"))},
    "cond_reduce": {"src": "cond.mlir", "gen": lambda: (
        _wf(f"{SEC}/cond_reduce_A.bin", [0.0] * 4096, "f"),     # sum 0 -> else
        _wf(f"{SEC}/cond_reduce_B.bin", [1.0] * 4096, "f"))},   # sum>0 -> if
    "mask_select": {"src": "select.mlir", "gen": lambda: (
        _wf(f"{SEC}/mask_select_A.bin", [0] * 4096, "B"),       # all-false mask
        _wf(f"{SEC}/mask_select_B.bin", [1] * 4096, "B"))},     # all-true mask
    "idx_gather": {"src": "gather.mlir", "gen": lambda: (
        _wf(f"{SEC}/idx_gather_A.bin", [0] * 4096, "i"),        # all read table[0]
        _wf(f"{SEC}/idx_gather_B.bin", [_R.randrange(256) for _ in range(4096)], "i"))},
    # tensor-source variants for the bufferization pipeline P4 (same secrets).
    "matvec_t": {"src": "matvec_t.mlir", "gen": lambda: (
        _wf(f"{SEC}/matvec_t_A.bin", [0.0] * (256 * 256), "f"),
        _wf(f"{SEC}/matvec_t_B.bin", [_R.gauss(0, 1) for _ in range(256 * 256)], "f"))},
    "mask_select_t": {"src": "select_t.mlir", "gen": lambda: (
        _wf(f"{SEC}/mask_select_t_A.bin", [0] * 4096, "B"),
        _wf(f"{SEC}/mask_select_t_B.bin", [1] * 4096, "B"))},
    # dynamic-shape: the secret IS the extent k. A=1 (tiny), B=4096 (full).
    "dynshape": {"src": "dynshape.mlir", "gen": lambda: (
        _wf(f"{SEC}/dynshape_A.bin", [1], "i"),
        _wf(f"{SEC}/dynshape_B.bin", [4096], "i"))},
    "dynshape_t": {"src": "dynshape_t.mlir", "gen": lambda: (   # tensor-source, P4
        _wf(f"{SEC}/dynshape_t_A.bin", [1], "i"),
        _wf(f"{SEC}/dynshape_t_B.bin", [4096], "i"))},
}


def gen_secrets(kernels):
    os.makedirs(SEC, exist_ok=True)
    for k in kernels:
        KERNELS[k]["gen"]()


def build(pipeline, kernels, backend):
    """Lower each kernel through `pipeline`; kernels that fail to lower/compile are
    skipped (their weak symbol stays unlinked). Link one binary per (pipeline,opt)
    with the survivors. Returns (bin_path, set_of_ok_kernels)."""
    os.makedirs(BUILD, exist_ok=True)
    passes = list(PIPELINES[pipeline])
    tag = f"{pipeline}_{backend[1].lstrip('-')}"
    objs, ok = [], set()
    for k in kernels:
        src = os.path.join(HERE, KERNELS[k]["src"])
        lo = os.path.join(BUILD, f"{k}.{tag}.mlir")
        ll = os.path.join(BUILD, f"{k}.{tag}.ll")
        obj = os.path.join(BUILD, f"{k}.{tag}.o")
        try:
            subprocess.run([MLIR_OPT, src, *passes, *TAIL.split(), "-o", lo],
                           check=True, capture_output=True)
            subprocess.run([MLIR_TRANSLATE, "--mlir-to-llvmir", lo, "-o", ll],
                           check=True, capture_output=True)
            subprocess.run([*backend, "-c", ll, "-o", obj], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            continue  # this kernel does not lower under this pipeline -> cell "-"
        objs.append(obj); ok.add(k)
    binp = os.path.join(BUILD, f"mlir_{tag}")
    subprocess.run([*backend, "-I/usr/include", "-o", binp,
                    os.path.join(HERE, "mlir_driver.c"), *objs],
                   check=True, stderr=subprocess.DEVNULL)
    return binp, ok


# --- broadened TAINT parser (control-flow AND address/value leaks) -------------
_CF = re.compile(r"depends on uninitialised value", re.I)        # branch/move
_ADDR = re.compile(r"use of uninitialised value|invalid (read|write)", re.I)  # address
_BEGIN, _END = "taint region begin", "taint region end"


def taint_check(binp, kernel, secret):
    """Run memcheck, parse reports strictly inside the marked region, classify the
    leak: 'cf' (control-flow), 'addr' (address/value), or '' (clean)."""
    with tempfile.NamedTemporaryFile(suffix=".mc", delete=False) as f:
        log = f.name
    try:
        vg = ["valgrind", "--tool=memcheck", "--track-origins=yes",
              "--error-exitcode=0", f"--log-file={log}"]
        subprocess.run(vg + [binp, kernel, secret, "taint"], cwd=HERE,
                       env=I._env(), timeout=I.TIMEOUT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        kind, inreg = "", False
        with open(log, errors="replace") as fh:
            for line in fh:
                if _BEGIN in line: inreg = True; continue
                if _END in line: inreg = False; continue
                if inreg and _CF.search(line): kind = "cf"
                elif inreg and not kind and _ADDR.search(line): kind = "addr"
        return kind
    finally:
        try: os.unlink(log)
        except OSError: pass


_DECISION_KEYS = ("Ir", "Bc", "Dw")


def _sample_fn(binp, kernel):
    def sample(secret_path):
        return I.callgrind_count_cmd(
            [binp, kernel, secret_path, "count"], cwd=HERE, cache_sim=True
        )

    return sample


def analyze(binp, kernel, pa, pb, reps=5):
    """
    Context-varying paired counts on Ir/Bc/Dw, with noninterference.py's
    floor+stability guard (reused via differential.py, not re-derived) +
    broadened taint (cf/addr). leak = count-distinguishable OR taint.
    """
    sample = _sample_fn(binp, kernel)
    with NI.context_dir() as d:
        rows_zero = D.sample_over_contexts(sample, pa, reps, d, NI._context)
        rows_rand = D.sample_over_contexts(sample, pb, reps, d, NI._context)
    kind = taint_check(binp, kernel, pb)
    taint = {"leak": bool(kind), "kind": kind}
    v = D.compute_verdict_from_rows(rows_zero, rows_rand, _DECISION_KEYS, _DECISION_KEYS, taint)
    return dict(
        leak=v["distinguishable"],
        taint=kind,
        ir_sep=v["stables"]["Ir"] and abs(v["diffs"]["Ir"]) > v["floors"]["Ir"],
        bc_sep=v["stables"]["Bc"] and abs(v["diffs"]["Bc"]) > v["floors"]["Bc"],
        dw_sep=v["stables"]["Dw"] and abs(v["diffs"]["Dw"]) > v["floors"]["Dw"],
        dIr=v["diffs"]["Ir"],
        dBc=v["diffs"]["Bc"],
        dDw=v["diffs"]["Dw"],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernels", nargs="+",
                    default=["matvec", "cond_reduce", "mask_select", "idx_gather"])
    ap.add_argument("--pipelines", nargs="+", default=["P0", "P1", "P2", "P3", "P5"])
    ap.add_argument("--opt", default="O0", choices=["O0", "O2", "O3"],
                    help="LLVM backend optimization level (the second axis)")
    args = ap.parse_args()

    backend = [CLANG, f"-{args.opt}", "-mavx2", "-mno-avx512f"]
    gen_secrets(args.kernels)
    print(f"Building {len(args.pipelines)} pipeline(s) x {len(args.kernels)} kernel(s), "
          f"backend {' '.join(backend)} ...")
    bins = {p: build(p, args.kernels, backend) for p in args.pipelines}

    print("\nLEAK MATRIX (L=distinguishable  .=oblivious  -=did not lower)  "
          f"[opt={args.opt}]")
    print(f"[verdict per cell is relative to baseline pipeline {args.pipelines[0]!r}; "
          "see DETAIL below]\n")
    print(f"{'kernel':<14} " + "  ".join(f"{p:>4}" for p in args.pipelines))
    details = []
    for k in args.kernels:
        pa, pb = f"{SEC}/{k}_A.bin", f"{SEC}/{k}_B.bin"
        cells = []
        for p in args.pipelines:
            binp, ok = bins[p]
            if k not in ok:
                cells.append("-"); continue
            r = analyze(binp, k, pa, pb)
            cells.append("L" if r["leak"] else ".")
            details.append((k, p, r))
        print(f"{k:<14} " + "  ".join(f"{c:>4}" for c in cells))

    # Automatic verdict relative to the first pipeline given (default P0),
    # replacing "read the matrix by eye and infer compiler-introduced" with
    # a computed field -- same quadrant differential.verdict_relative_to_baseline
    # generalizes from noninterference.py's authored/compiler-introduced/
    # compiler-removed/oblivious.
    baseline_pipeline = args.pipelines[0]
    baseline_leak = {k: r["leak"] for k, p, r in details if p == baseline_pipeline}

    print("\nDETAIL (taint: cf=control-flow, addr=address; counts corroborate)")
    for k, p, r in details:
        chan = []
        if r["taint"]: chan.append(f"taint:{r['taint']}")
        if r["ir_sep"]: chan.append(f"Ir(dIr={r['dIr']:+d})")
        if r["bc_sep"]: chan.append(f"Bc(dBc={r['dBc']:+d})")
        if r["dw_sep"]: chan.append(f"Dw(dDw={r['dDw']:+d})")
        verdict = D.verdict_relative_to_baseline(baseline_leak.get(k, r["leak"]), r["leak"])
        print(f"  {k:<14} {p:<4} {'LEAK ' if r['leak'] else 'obliv'}  {verdict:<28} "
              f"{' '.join(chan) or 'clean'}")


if __name__ == "__main__":
    main()
