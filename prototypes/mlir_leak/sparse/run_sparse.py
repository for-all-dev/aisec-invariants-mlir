"""
The sparsifier finding, on the shared differential engine.

`--sparsification` lowers a linalg.generic over a sparse tensor into
iteration over STORED coordinates, so the store address `out[crd[i]]`
depends on the secret sparsity PATTERN, while the dense lowering of the same
computation is oblivious. That makes this the one case in this study where
an *optimizing* pass manufactures the channel (../README.md finding 8) --
the strongest result here, and the reason it should not be the least
verified one.

It used to be exactly that: a copy-paste shell recipe in README.md with no
runner, so unlike every other kernel in this prototype it never went through
leak_check's instruments, never got the context-varying floor/stability
guard, and could not be re-validated by running anything. This script closes
that gap -- same engine, same guards, same verdict vocabulary as
../run_mlir.py.

    python3 run_sparse.py             # sparse vs dense lowering of one kernel
    python3 run_sparse.py --reps 7

The comparison is DIFFERENTIAL against an oblivious reference, which is what
makes "the optimization introduced it" a computed verdict rather than a
claim: scatter.mlir under --sparsifier (iterate stored coordinates) is
measured against scatter_dense.mlir (visit every dense position, secret
never an address), on the same two secret classes. Baseline is the DENSE
build.

The verdict is taken on the ADDRESS channel specifically, not on a
leak/no-leak bit. Both builds consume the secret, and memcheck's
control-flow message covers a conditional jump OR MOVE -- i.e. any
comparison -- so the dense reference trips `cf` merely by comparing
coordinates against positions, however branchlessly. What --sparsification
is claimed to introduce is a secret-dependent ADDRESS, so that is what is
compared; measured result: dense has no address channel, sparse does.
"""

import argparse
import array
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "leak_check")))
import differential as D
import instruments as I
import noninterference as NI

BUILD = os.path.join(HERE, "build")
SEC = os.path.join(HERE, "secrets")
# Measurement-context dirs live under THIS prototype, not leak_check's tree.
_CTX_ROOT = os.path.join(SEC, "_ctx")
MLIR_OPT, MLIR_TRANSLATE, CLANG = "mlir-opt-18", "mlir-translate-18", "clang-18"

NNZ = 8
DENSE = 256

# The two builds. "sparse" is the optimization under test: the sparsifier
# turns scatter.mlir's sparse-encoded tensor into iteration over stored
# coordinates. "dense" is the oblivious reference it must be judged against
# -- without a reference, "the sparse build leaks" is a fact about the
# kernel, not about the pass.
#
# The reference is a separate source, not another pipeline over the same
# one, and that is forced rather than chosen: scatter.mlir's
# sparse_tensor.assemble/convert cannot be legalized WITHOUT sparsification
# (mlir-18 rejects `sparse_tensor.convert` as illegal on the
# --sparse-tensor-conversion path), so "the same IR lowered densely" does
# not exist. scatter_dense.mlir instead expresses the same result-by-
# construction obliviously; see its header for why it avoids arith.select.
LOWERINGS = {
    "sparse": ("scatter.mlir", ["--sparsifier=enable-runtime-library=false"]),
    "dense": ("scatter_dense.mlir", ["--convert-scf-to-cf", "--expand-strided-metadata"]),
}

TAIL = ("--convert-index-to-llvm --convert-cf-to-llvm --convert-arith-to-llvm "
        "--finalize-memref-to-llvm --convert-func-to-llvm --reconcile-unrealized-casts")

# Secret = the nonzero COORDINATES. Both classes have identical nnz and
# identical values/positions, so nothing but the pattern differs -- any
# dependence is the pattern, not the amount of work.
CLASS_A = [0, 1, 2, 3, 4, 5, 6, 7]           # tightly packed
CLASS_B = [3, 29, 61, 97, 130, 168, 201, 240]  # spread across the dense range


def gen_secrets():
    os.makedirs(SEC, exist_ok=True)
    for name, crd in (("A", CLASS_A), ("B", CLASS_B)):
        assert len(crd) == NNZ and all(0 <= c < DENSE for c in crd)
        array.array("q", crd).tofile(open(os.path.join(SEC, f"crd_{name}.bin"), "wb"))


def build(name):
    """Lower this build's source under its pipeline and link the driver."""
    os.makedirs(BUILD, exist_ok=True)
    src, passes = LOWERINGS[name]
    lo = os.path.join(BUILD, f"scatter.{name}.mlir")
    ll = os.path.join(BUILD, f"scatter.{name}.ll")
    obj = os.path.join(BUILD, f"scatter.{name}.o")
    binp = os.path.join(BUILD, f"scatter_{name}")
    subprocess.run([MLIR_OPT, os.path.join(HERE, src),
                    *passes, *TAIL.split(), "-o", lo],
                   check=True, capture_output=True)
    subprocess.run([MLIR_TRANSLATE, "--mlir-to-llvmir", lo, "-o", ll],
                   check=True, capture_output=True)
    subprocess.run([CLANG, "-O0", "-c", ll, "-o", obj], check=True, capture_output=True)
    subprocess.run([CLANG, "-O0", "-I/usr/include", "-o", binp,
                    os.path.join(HERE, "sparse_driver.c"), obj],
                   check=True, capture_output=True)
    return binp


# Same channels and same decision set as ../run_mlir.py, for the same reason
# (the address channel is a Dw/taint finding, invisible on Ir/Bc alone);
# pinned by leak_check/tests/test_differential.py.
_DECISION_KEYS = ("Ir", "Bc", "Dw")


def analyze(binp, pa, pb, reps):
    def sample(secret_path):
        return I.callgrind_count_cmd([binp, secret_path, "count"], cwd=HERE, cache_sim=True)

    with NI.context_dir(root=_CTX_ROOT) as d:
        rows_zero = D.sample_over_contexts(sample, pa, reps, d, NI._context)
        rows_rand = D.sample_over_contexts(sample, pb, reps, d, NI._context)
    taint = I.memcheck_taint_cmd([binp, pb, "taint"], cwd=HERE, classify=True)
    kinds = taint["kinds"]
    v = D.compute_verdict_from_rows(
        rows_zero, rows_rand, _DECISION_KEYS, _DECISION_KEYS, {"leak": bool(kinds)}
    )
    return {
        "leak": v["distinguishable"], "kinds": kinds,
        # The address channel is the claim under test: --sparsification makes
        # the STORE ADDRESS depend on the secret pattern. Tracked separately
        # because a leak/no-leak bit cannot express "which channel", and
        # because cf fires for both builds here (see the header).
        "addr": "addr" in kinds,
        "dIr": v["diffs"]["Ir"], "dBc": v["diffs"]["Bc"], "dDw": v["diffs"]["Dw"],
        "counts": v["counts_distinguish"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5, help="measurement contexts per class")
    args = ap.parse_args()

    gen_secrets()
    pa, pb = os.path.join(SEC, "crd_A.bin"), os.path.join(SEC, "crd_B.bin")

    print("Building dense (baseline) and sparse lowerings of scatter.mlir ...")
    results = {}
    for name in ("dense", "sparse"):
        try:
            binp = build(name)
        except subprocess.CalledProcessError as e:
            print(f"  {name:<7} DID NOT LOWER/BUILD: {e.stderr.decode(errors='replace')[:300]}")
            continue
        results[name] = analyze(binp, pa, pb, args.reps)

    base = results.get("dense")
    print("\nVerdict is on the ADDRESS channel: both builds consume the secret, so")
    print("both trip memcheck's cf channel (it covers a conditional jump OR MOVE,")
    print("i.e. any comparison), and a leak/no-leak bit cannot separate them. What")
    print("--sparsification is claimed to introduce is a secret-dependent ADDRESS.\n")
    print(f"  {'LOWERING':<10} {'ADDR':<6} {'VERDICT (addr channel)':<34} CHANNELS")
    for name, r in results.items():
        chan = [f"taint:{k}" for k in r["kinds"]]
        if r["counts"]:
            chan.append(f"Ir(dIr={r['dIr']:+d}) Bc(dBc={r['dBc']:+d}) Dw(dDw={r['dDw']:+d})")
        verdict = ("baseline-cell" if name == "dense"
                   else "baseline-did-not-build" if base is None
                   else D.verdict_relative_to_baseline(base["addr"], r["addr"]))
        print(f"  {name:<10} {('yes' if r['addr'] else 'no'):<6} {verdict:<34} "
              f"{' '.join(chan) or 'clean'}")


if __name__ == "__main__":
    main()
