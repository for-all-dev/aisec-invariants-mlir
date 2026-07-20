"""
Escalate the freezing constant-fold leak from a codegen-DIFF to an instruction-
/data-level proof of the secret -> literal causal flow.

Established finding (leak_check.freezing.agents.md): with
`torch._inductor.config.freezing = True`, Inductor constant-folds the quantization
scale `max|w|/127` and emits it as a `static_cast<float>` literal in the generated
C++. Two secret classes (max|w| = 1.0 vs 100.0) yield frozen kernels differing by
exactly that literal; the non-frozen compile of the same source is byte-identical.
That is proven at the codegen-diff level. This probe escalates it two ways.

THE CRITICAL INSIGHT: the fold happens at COMPILE time. In the frozen model the
executed kernel reads the folded LITERAL, not the weight buffer, so the classic
RUNTIME taint (mark weights undefined, run the forward under memcheck) reads CLEAN
on the frozen model. The secret was exfiltrated into the code during compilation.
So the taint must be applied to the COMPILE step.

Two proof paths, reported independently (a clean negative on either is still a
result -- PRINCIPLES §1):

  [1] COMPILE-TIME TAINT (memcheck).  Mark the weight bytes UNDEFINED, then compile
      frozen UNDER memcheck (--track-origins). The constant-folding pass reads the
      tainted bytes to compute max|w|/127; memcheck should report the use with
      ORIGIN = the weight buffer (a Valgrind client request), at a compile/codegen
      site. Negative control: the SAME source compiled NON-frozen must NOT produce a
      compile-site weight-origin report (no literal is emitted) -- isolating
      FREEZING, not compilation, as the cause. This channel is a RUNTIME channel;
      whether it sees a compile-time fold is exactly the open question, so a blind
      result here is reported honestly and the functional-dependence path carries
      the proof.

  [2] FUNCTIONAL DEPENDENCE (deterministic, no valgrind).  Perturb a SINGLE weight
      element to a swept value v (making it the max), recompile frozen, and recover
      the emitted literal. If literal == v/127 across the sweep to float32 precision,
      the emitted constant is a measured, exact function of the secret -- a
      secret -> literal map, stronger than "two classes differ".

    uv run python probe_freezing_taint.py            # both paths
    uv run python probe_freezing_taint.py fd         # functional-dependence only
    uv run python probe_freezing_taint.py taint      # compile-time taint only
"""

import getpass
import os
import re
import subprocess
import sys

import numpy as np

import corpus_freezing as CF
from probe_freezing import recover_literal, redact, run

HERE = os.path.dirname(os.path.abspath(__file__))
SEC = os.path.join(HERE, "secrets", "freeze")
TAINT_TIMEOUT = int(os.environ.get("LEAKCHECK_TAINT_TIMEOUT", "28800"))  # 8h default
_USER = getpass.getuser()
_HOME = os.path.expanduser("~")
_HOME_RE = re.compile(r"/home/[^/ )\n]+")


def redact_out(text):
    """redact() (repo root + inductor user) plus any absolute /home/<user> path, so a
    recorded .out carries no PII (see leak_check.count-confound.agents.md)."""
    text = redact(text).replace(_HOME, "<home>")
    return _HOME_RE.sub("/home/<user>", text)


def ensure_shim():
    so = os.path.join(HERE, "vgshim.so")
    src = os.path.join(HERE, "vgshim.c")
    if not os.path.exists(so) or os.path.getmtime(so) < os.path.getmtime(src):
        subprocess.run(["g++", "-shared", "-fPIC", "-O0", src, "-o", so], check=True)
    return so


# ---------------------------------------------------------------------------
# [1] Compile-time taint under memcheck
# ---------------------------------------------------------------------------

# A memcheck report block starts with one of these "kind" lines and runs until the
# next blank ==PID== line. --track-origins appends an origin sub-block whose first
# line names how the uninitialised value was created; "client request" is OUR
# vg_make_undefined on the weight buffer -- the only tainted memory in the process.
_PID = re.compile(r"^==\d+==\s?")
_KIND = re.compile(
    r"(Use of uninitialised value|Conditional jump or move depends on uninitialised value|"
    r"depends on uninitialised value|uninitialised (?:byte|value)s?)",
    re.I,
)
_ORIGIN = re.compile(r"Uninitialised value was created", re.I)
_CLIENT = re.compile(r"created by a client request", re.I)
_BEGIN = "taint region begin"
_END = "taint region end"

# Frame signatures, classified by precedence emit > kernel > codegen:
#
#  EMIT  : the value is being FORMATTED into a string -- the C++ source literal is
#          written here (Python float formatting: format_float_internal /
#          PyOS_double_to_string / _PyFloat_Format...). A "depends on uninitialised
#          value" here means the number being serialized into the generated code is
#          undefined, i.e. secret-derived. THIS is the fold reaching the emitted
#          code; it is the signal the escalation is after.
#  KERNEL: a compiled inductor kernel .so (temp path under the private cache, or a
#          cpp_fused/kernel symbol) -- the ordinary RUNTIME read, not the fold.
#  CODEGEN: elsewhere in libtorch / interpreter / inductor (the fold's aten reduction
#          runs here, but a report here need not be the literal emission).
_EMIT_SITE = re.compile(
    r"(format_float|PyOS_double_to_string|_PyFloat_Format|float___format__|"
    r"float_repr|_Py_dg_dtoa)"
)
_KERNEL_SITE = re.compile(
    r"(cpp_fused|kernel_|/ic_freeze_taint_|torchinductor|/tmp/tmp\w+/[a-z0-9]{2}/c)"
)
_COMPILE_SITE = re.compile(
    r"(libtorch_cpu|libtorch\.so|_inductor|constant_fold|ConstantFold|libc10|"
    r"aten|at::native|python3|libpython|_C\.)",
    re.I,
)


def _strip(line):
    return _PID.sub("", line.rstrip("\n"))


def parse_memcheck_log(path):
    """Return report blocks that fall strictly inside the taint region.

    Each block: {kind, weight_origin(bool), site(str), error_frames[list],
    origin_line(str), origin_frames[list]}. `site` in {emit, kernel, codegen,
    unknown}."""
    reports = []
    in_region = False
    with open(path, errors="replace") as fh:
        lines = fh.readlines()

    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        s = _strip(raw)
        if _BEGIN in s:
            in_region = True
            i += 1
            continue
        if _END in s:
            in_region = False
            i += 1
            continue
        if in_region and _KIND.search(s) and not _ORIGIN.search(s):
            kind = s.strip()
            error_frames = []
            origin_line = ""
            origin_frames = []
            weight_origin = False
            in_origin = False
            i += 1
            # consume until blank ==PID== separator
            while i < n:
                s2 = _strip(lines[i])
                if s2.strip() == "":
                    break
                if _ORIGIN.search(s2):
                    in_origin = True
                    origin_line = s2.strip()
                    if _CLIENT.search(s2):
                        weight_origin = True
                elif s2.strip().startswith(("at ", "by ")):
                    (origin_frames if in_origin else error_frames).append(s2.strip())
                i += 1
            joined = " ".join(error_frames)
            if _EMIT_SITE.search(joined):
                site = "emit"
            elif _KERNEL_SITE.search(joined):
                site = "kernel"
            elif _COMPILE_SITE.search(joined):
                site = "codegen"
            else:
                site = "unknown"
            reports.append(
                {
                    "kind": kind,
                    "weight_origin": weight_origin,
                    "site": site,
                    "error_frames": error_frames,
                    "origin_line": origin_line,
                    "origin_frames": origin_frames,
                }
            )
            continue
        i += 1
    return reports


def run_taint_arm(mode, secret_path, log_path):
    """Compile one arm under memcheck, writing the full log to log_path."""
    ensure_shim()
    env = dict(
        os.environ,
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        PYTHONHASHSEED="0",
    )
    vg = [
        "valgrind",
        "--tool=memcheck",
        "--track-origins=yes",
        "--error-exitcode=0",
        "--trace-children=no",
        "--num-callers=40",
        f"--log-file={log_path}",
    ]
    cmd = vg + [sys.executable, "_freezing_taint_worker.py", "quant_scale", secret_path, mode]
    subprocess.run(
        cmd, cwd=HERE, env=env, timeout=TAINT_TIMEOUT, stdout=subprocess.DEVNULL, check=False
    )
    return log_path


def taint_experiment(reuse_dir=None):
    (la, a), (_lb, _b), (_lc, _c) = CF.secret_classes("quant_scale")
    pa = os.path.join(SEC, f"quant_scale_{la}.npy")
    os.makedirs(SEC, exist_ok=True)
    np.save(pa, a)
    exp = CF.stat("quant_scale", a)

    print("=" * 78)
    print("[1] COMPILE-TIME TAINT  (memcheck --track-origins on the compile step)")
    print("=" * 78)
    print(
        f"  secret class {la}: max|w|={float(np.max(np.abs(a))):.6g}  ->  fold max|w|/127 = {exp:.9g}"
    )
    print("  positive arm: FROZEN compile with weight bytes UNDEFINED")
    print("  negative arm: NON-FROZEN compile, same source, same taint (control)")
    print("  the escalation looks for an in-region report at the literal-EMIT site (the")
    print("  Python float formatter that writes the constant into the generated C++);")
    print("  present frozen, absent non-frozen => the tainted value reaches the emitted")
    print("  code and freezing is the cause. Whether --track-origins can further NAME")
    print("  the weight buffer (client-request origin) is the open channel question.\n")

    out = {}
    for mode in ("frozen", "nonfrozen"):
        log = (
            os.path.join(reuse_dir, f"mc_{mode}.mc")
            if reuse_dir
            else os.path.join(SEC, "taint", f"mc_{mode}.mc")
        )
        if not reuse_dir:
            os.makedirs(os.path.dirname(log), exist_ok=True)
            print(f"  running {mode} arm under memcheck (slow) ...", flush=True)
            run_taint_arm(mode, pa, log)
        reports = parse_memcheck_log(log)
        emit = [r for r in reports if r["site"] == "emit"]
        weight = [r for r in reports if r["weight_origin"]]  # client-request origin
        emit_weight = [r for r in emit if r["weight_origin"]]
        markers = _count_markers(log)
        out[mode] = {
            "reports": reports,
            "emit": emit,
            "weight_origin": weight,
            "emit_weight": emit_weight,
            "markers": markers,
        }
        print(f"  --- {mode} ---")
        print(f"    taint-region markers in log: {markers} (2 = begin+end bracket the compile)")
        print(f"    in-region 'uninitialised' reports: {len(reports)}")
        print(f"      at the literal-EMIT (float format) site : {len(emit)}")
        print(f"      with origin traced to the weight buffer : {len(weight)} (client request)")
        for r in emit[:1]:
            print(f"      sample emit-site report [{r['kind']}]:")
            for fr in r["error_frames"][:3]:
                print("         err: " + redact_out(fr))
            if r["origin_line"]:
                print("         " + redact_out(r["origin_line"]))
            for fr in r["origin_frames"][:1]:
                print("         org: " + redact_out(fr))
        print()

    fz, nf = out["frozen"], out["nonfrozen"]
    d = decide_taint(
        {"markers": fz["markers"], "emit": len(fz["emit"]), "emit_weight": len(fz["emit_weight"])},
        {"markers": nf["markers"], "emit": len(nf["emit"]), "emit_weight": len(nf["emit_weight"])},
    )
    print("  RESULT[compile-time-taint]:")
    print(f"    frozen emit-site reports    : {len(fz['emit'])}")
    print(f"    non-frozen emit-site reports: {len(nf['emit'])}  (control must be 0)")
    print(
        f"    frozen emit report NAMES the weight buffer (client-request origin): {d['origin_named']}"
    )
    if d["proven_origin"]:
        print("    VERDICT: INSTRUCTION-LEVEL PROOF (origin = weight buffer) -- memcheck")
        print("             fires at the literal emission AND traces the origin to the")
        print("             tainted weight; the non-frozen control is silent.")
    elif d["emit_isolated"]:
        print("    VERDICT: INSTRUCTION-LEVEL SIGNAL, isolated to freezing -- memcheck")
        print("             fires at the literal-emit site (float formatter) only under")
        print("             freezing; the value serialized into the generated C++ is")
        print("             UNDEFINED (secret-derived). --track-origins does NOT name the")
        print("             weight buffer: it severs at the aten reduction's c10::Scalar,")
        print("             one hop from the weight. So the fold-reaches-code step is")
        print("             proven at the instruction level; the byte-exact origin is not.")
    elif d["blind"]:
        print("    VERDICT: CHANNEL BLIND -- markers bracket the compile but no emit-site")
        print("             report fired. The runtime taint channel did not observe the")
        print("             compile-time fold. Functional-dependence [2] carries the proof.")
    else:
        print("    VERDICT: INCONCLUSIVE -- see per-arm classification above.")
    out["verdict"] = d
    return out


def decide_taint(frozen, nonfrozen):
    """Pure verdict from classified in-region report COUNTS (testable without valgrind).

    frozen/nonfrozen dicts carry: markers, emit (reports at the float-format/literal-
    emit site), emit_weight (emit reports whose --track-origins origin is the weight
    buffer, i.e. a Valgrind client request).

    - proven_origin  : the strongest form -- an emit-site report in the frozen arm whose
      origin is the weight buffer, with the non-frozen control silent at emit sites.
    - emit_isolated  : an emit-site report fires under freezing and NOT in the non-frozen
      control -- the tainted (secret-derived) value reaches the emitted code, isolated to
      freezing -- even though --track-origins does not name the weight buffer.
    - blind          : markers bracketed the frozen compile yet no emit-site report fired.
    """
    control_silent = nonfrozen["emit"] == 0
    origin_named = frozen["emit_weight"] > 0
    emit_isolated = frozen["emit"] > 0 and control_silent
    proven_origin = origin_named and emit_isolated
    blind = frozen["markers"] == 2 and frozen["emit"] == 0
    return {
        "control_silent": control_silent,
        "origin_named": origin_named,
        "emit_isolated": emit_isolated,
        "proven_origin": proven_origin,
        "blind": blind,
    }


def _count_markers(path):
    c = 0
    with open(path, errors="replace") as fh:
        for line in fh:
            if _BEGIN in line or _END in line:
                c += 1
    return c


# ---------------------------------------------------------------------------
# [2] Functional dependence: literal == v/127 as v sweeps a single weight element
# ---------------------------------------------------------------------------
def functional_dependence(sweep=(1.0, 1.0009765625, 1.5, 2.0, 5.0, 42.0, 100.0)):
    """Fix a base weight (all |.|<=0.9), then set ONE element to v so max|w|==v, and
    recover the frozen literal. literal must equal v/127 to float32 precision, and
    the map v -> literal must be exactly linear with slope 1/127."""
    d = os.path.join(SEC, "fd")
    os.makedirs(d, exist_ok=True)
    base = np.random.default_rng(11).standard_normal((CF.DIM, CF.DIM)).astype(np.float32)
    base = base / np.max(np.abs(base)) * np.float32(0.9)

    print("=" * 78)
    print("[2] FUNCTIONAL DEPENDENCE  (deterministic; single-element perturbation)")
    print("=" * 78)
    print("  base weight |.|<=0.9; element [0,0] set to v (the new max); surface=quant_scale")
    print("  expected folded literal = v/127 (float32). Recover it from the frozen kernel.\n")
    print(
        f"  {'v (max|w|)':>14}  {'expected v/127':>18}  {'recovered literal':>20}  {'abs err':>12}  match"
    )
    rows = []
    for v in sweep:
        w = base.copy()
        w[0, 0] = np.float32(v)
        p = os.path.join(d, f"v_{v:.8g}.npy")
        np.save(p, w)
        exp = CF.stat("quant_scale", w)  # == v/127 in float32
        _res, code, _raw = run("quant_scale", p, "frozen")
        rec = recover_literal(code, exp, tol=1e-2)
        ok = rec is not None and abs(rec - exp) <= 1e-6 * abs(exp)
        err = abs(rec - exp) if rec is not None else float("nan")
        rows.append((v, exp, rec, ok))
        rec_s = f"{rec:.12g}" if rec is not None else "NONE"
        print(f"  {v:>14.9g}  {exp:>18.12g}  {rec_s:>20}  {err:>12.3g}  {ok}")

    # Linearity: recovered literal is an exact affine function of v with slope 1/127.
    vs = np.array([r[0] for r in rows], dtype=np.float64)
    recs = np.array([r[2] if r[2] is not None else np.nan for r in rows], dtype=np.float64)
    all_match = all(r[3] for r in rows)
    slope = None
    if np.all(np.isfinite(recs)) and len(vs) >= 2:
        slope = float(np.polyfit(vs, recs, 1)[0])
    print()
    print(f"  all literals equal v/127 to float32 precision: {all_match}")
    if slope is not None:
        print(f"  fitted slope d(literal)/d(v) = {slope:.10g}  (1/127 = {1.0 / 127.0:.10g})")
    print("  RESULT[functional-dependence]:")
    if all_match:
        print("    VERDICT: MEASURED SECRET->LITERAL MAP. The emitted constant is an")
        print("             exact function of the secret: perturbing one weight element")
        print("             by dv moves the baked-in literal by exactly dv/127.")
    else:
        print("    VERDICT: literal did not track v/127 across the sweep (see rows).")
    return {"rows": rows, "all_match": all_match, "slope": slope}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    reuse = os.environ.get("LEAKCHECK_TAINT_LOGDIR")  # analyze pre-run logs if set
    print("Freezing weight-fold: instruction-/data-level escalation of the codegen-diff finding")
    print(f"torch {__import__('torch').__version__}\n")
    results = {}
    if which in ("all", "fd"):
        results["fd"] = functional_dependence()
        print()
    if which in ("all", "taint"):
        results["taint"] = taint_experiment(reuse_dir=reuse)
        print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    if "fd" in results:
        print(
            f"  functional-dependence : {'PROVEN (literal == max|w|/127 exactly)' if results['fd']['all_match'] else 'not shown'}"
        )
    if "taint" in results:
        v = results["taint"]["verdict"]
        tag = (
            "INSTRUCTION-LEVEL PROOF (origin = weight buffer)"
            if v["proven_origin"]
            else "INSTRUCTION-LEVEL SIGNAL at the literal-emit site, isolated to freezing"
            if v["emit_isolated"]
            else "CHANNEL BLIND (runtime channel; see [2])"
            if v["blind"]
            else "INCONCLUSIVE"
        )
        print(f"  compile-time taint    : {tag}")


if __name__ == "__main__":
    main()
