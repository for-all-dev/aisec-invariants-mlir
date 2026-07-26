"""
Differential staging non-interference across MLIR lowering pipelines --
statically.

This is `../mlir_leak`'s question ("did a lowering pass introduce or remove
the leak?") asked of the static checker instead of a measurement, using the
same verdict vocabulary from `../leak_check/differential.py`. The checker is
run on the source IR, then the IR is lowered by `mlir-opt`, then the checker
is run again, and the two findings are compared:

    authored-and-survives   leak present before AND after   (the program's)
    lowering-introduced     absent before, present after    (the pass's)
    lowering-removed        present before, absent after
    oblivious               absent in both

    python3 staging_ni_diff.py kernel.mlir
    python3 staging_ni_diff.py ../mlir_leak/*.mlir --pipelines P0 P1
    python3 staging_ni_diff.py k.mlir --protect 0   # tag arg #0 protected

Why this exists: Staging_NI could previously only answer "does this IR, as
given, leak" -- a single snapshot, with no way to attribute anything to a
compilation step. That left the repository with two prototypes answering
overlapping questions at different levels of rigour, which is the thing the
unification work is meant to remove. The pipelines are `mlir_leak`'s own
PIPELINES table, imported rather than re-listed, so the two prototypes sweep
the same compiler axis by construction.

WHAT THIS CANNOT DO, and why it is stated up front: a static verdict is not
a measurement. `mlir_leak` compiles the kernel and observes a real binary,
so its verdict is evidence about what the machine does. This one is evidence
about what the IR says, under an over-approximating taint analysis that
reports UNKNOWN where it cannot model a construct. It is faster and needs no
harness per kernel, and it covers all inputs rather than the two secret
classes a measurement exercises -- but where the two disagree, the
measurement is the ground truth, not this.

UNKNOWN is not folded into "no leak". A pipeline whose lowered form the
checker cannot model reports `unknown-after` (and `unknown-before` for the
source), never `lowering-removed`: "the analysis stopped being able to see
it" and "the leak is gone" are different findings, and conflating them is
exactly how a differential check manufactures a false clean bill. The
checker's ability to survive the standard lowerings is itself pinned by
test/survives-lowering.mlir.
"""

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "leak_check")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "mlir_leak")))
import differential as D  # noqa: E402

STAGING_NI_OPT = os.path.join(HERE, "build", "tools", "staging-ni-opt")
MLIR_OPT = "mlir-opt-18"

# The compiler axis, taken from mlir_leak rather than duplicated, so both
# prototypes sweep the same pipelines by construction. Imported lazily so
# this script still runs if that prototype is absent.
try:
    from run_mlir import PIPELINES
except ImportError:  # pragma: no cover - only if mlir_leak is missing
    PIPELINES = {"P0": ["--convert-linalg-to-loops", "--convert-scf-to-cf",
                        "--expand-strided-metadata"]}

_VIOLATION = re.compile(r"error: Staging Non-Interference violation: (.+)")
_UNKNOWN = re.compile(r"remark: Staging Non-Interference: UNKNOWN - (.+?) \(unmodeled")


def check(path):
    """Run the checker. -> (violations, unknowns, ok) as reason lists."""
    p = subprocess.run([STAGING_NI_OPT, path, "--verify-staging-ni"],
                       capture_output=True, text=True)
    err = p.stderr
    # The pass signals failure on a confirmed violation, so a nonzero exit is
    # expected; only a *parse*/crash failure with no findings is a real error.
    violations = _VIOLATION.findall(err)
    unknowns = _UNKNOWN.findall(err)
    ok = bool(violations or unknowns) or p.returncode == 0
    return violations, unknowns, ok


def lower(path, pipeline, out):
    """Lower `path` through `pipeline`. -> True if it lowered."""
    r = subprocess.run([MLIR_OPT, path, *PIPELINES[pipeline], "-o", out],
                       capture_output=True, text=True)
    return r.returncode == 0


def protect_args(path, indices, out):
    """Tag the given function-argument positions `stagingni.protected`.

    mlir_leak's kernels carry no attribute (they are compiled and measured,
    not statically checked), so to run them here the secret has to be named.
    Deliberately textual and minimal -- it only adds the attribute to the
    listed positions of the FIRST func.func, and reports if it cannot.
    """
    src = open(path).read()
    m = re.search(r"func\.func @\w+\((.*?)\)", src, re.S)
    if not m:
        return False
    args = m.group(1).split(",")
    for i in indices:
        if i >= len(args):
            return False
        if "stagingni.protected" not in args[i]:
            args[i] = args[i].rstrip() + " {stagingni.protected}"
    patched = src[: m.start(1)] + ",".join(args) + src[m.end(1) :]
    open(out, "w").write(patched)
    return True


def verdict(before, after):
    """
    Same quadrant as differential.verdict_two_builds, with UNKNOWN kept as
    its own outcome instead of being read as "no leak".
    """
    b_leak, b_unknown = before
    a_leak, a_unknown = after
    if b_unknown and not b_leak:
        return "unknown-before"
    if a_unknown and not a_leak:
        return "unknown-after"
    return {
        "authored": "authored-and-survives",
        "compiler-introduced": "lowering-introduced",
        "compiler-removed": "lowering-removed",
        "oblivious": "oblivious",
    }[D.verdict_two_builds(b_leak, a_leak)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", help="MLIR files to check")
    ap.add_argument("--pipelines", nargs="+", default=["P0", "P1", "P2", "P5"])
    ap.add_argument("--protect", nargs="*", type=int, default=None,
                    help="function-argument indices to tag stagingni.protected")
    args = ap.parse_args()

    if not os.path.exists(STAGING_NI_OPT):
        sys.exit(f"{STAGING_NI_OPT} not built: cmake -B build && ninja -C build staging-ni-opt")

    tmp = os.path.join(HERE, "build", "diff")
    os.makedirs(tmp, exist_ok=True)

    print(f"{'kernel':<18} {'pipeline':<9} {'BEFORE':<10} {'AFTER':<10} VERDICT")
    for src in args.sources:
        name = os.path.basename(src).removesuffix(".mlir")
        path = src
        if args.protect:
            path = os.path.join(tmp, f"{name}.protected.mlir")
            if not protect_args(src, args.protect, path):
                print(f"{name:<18} {'-':<9} could not tag protected args")
                continue

        v0, u0, ok0 = check(path)
        if not ok0:
            print(f"{name:<18} {'-':<9} checker could not read the source IR")
            continue
        before = (bool(v0), bool(u0))

        for p in args.pipelines:
            out = os.path.join(tmp, f"{name}.{p}.mlir")
            if not lower(path, p, out):
                print(f"{name:<18} {p:<9} {'-':<10} {'-':<10} did-not-lower")
                continue
            v1, u1, ok1 = check(out)
            if not ok1:
                print(f"{name:<18} {p:<9} {'-':<10} {'-':<10} checker-failed-after")
                continue
            after = (bool(v1), bool(u1))
            fmt = lambda t: ("LEAK" if t[0] else "clean") + ("+unk" if t[1] else "")
            print(f"{name:<18} {p:<9} {fmt(before):<10} {fmt(after):<10} "
                  f"{verdict(before, after)}")


if __name__ == "__main__":
    main()
