"""
The differential non-interference criterion.

For one model we measure two secret classes (zero vs random) under two builds
(eager vs compiled), on two deterministic channels (callgrind Ir/Bc and memcheck
taint). A channel "distinguishes" the classes for a build iff:
    - callgrind: the instruction OR branch count differs between zero and random
      by more than the measured context floor, AND agrees across contexts
      (see below), or
    - memcheck : the secret produced a control-flow/address dependence.

Verdict:
    distinguishable under BOTH builds        -> "authored"   (source's fault)
    distinguishable ONLY after compilation   -> "compiler-introduced"
    distinguishable ONLY in eager            -> "compiler-removed"
    distinguishable under NEITHER            -> "oblivious"

Why a count needs a floor AND a stability check
-----------------------------------------------
`methodology.siddarth.md` ("Observation channels" 2) licenses a single run per
class: Ir is "exactly reproducible", so any difference is a real path. The first
half is true and the conclusion still does not follow.

Ir is exactly reproducible when a run is REPEATED (observed: spread 0 across
16/16 runs of one secret at one path). It is not reproducible when the
measurement CONTEXT changes underneath identical data: the same weights, md5-
identical, presented at two different file paths, count 99,212 vs 99,707. That
495 is larger than any dIr this corpus has ever called small -- larger than
softmax's -573, larger than branchless' +11/+257, larger than where_select's
+264.

Valgrind disables ASLR, so a run's layout is a deterministic function of its
argv/env. Two secret classes necessarily differ somewhere (at minimum, the file
they load), so the differential design cannot help but compare two contexts, and
a small dIr is confounded with that difference. Repeating a run at a fixed path
does not sample this at all -- it re-measures one context and reports spread 0,
which is why "repeat it and see" reads as confirmation.

So each repeat varies the context on purpose (`_context`), and both classes are
measured at the SAME context per repeat. That gives two independent guards:

  floor      -- how far a count moves when only the context changes. A diff
                under it is manufactured by the harness.
  stability  -- the paired diff must AGREE across contexts. A secret-dependent
                path gives the same diff in every layout; an artifact does not.

The stability check is the one that generalizes: it catches a large artifact,
which no magnitude test can. Both must pass for a count to distinguish.

This is asymmetric on purpose. Noise and layout manufacture false positives,
never false zeros: no layout makes a genuinely secret-dependent path count
identically in every context. So a count that fails either guard is NOT
INTERPRETABLE, which is weaker than "oblivious" (PRINCIPLES 1) -- resolve it
with the taint channel, which needs no magnitude difference at all.

repeats=1 degenerates to the original criterion (one context, floor 0, trivially
"stable"), so it reproduces the old numbers but inherits the old confound. It is
for comparison against the existing record, not for verdicts.
"""

import contextlib
import os
import shutil
import tempfile

import differential as D
import instruments as I

# Repeats per class per build. Each repeat is a distinct CONTEXT (see below).
# Cost is linear; callgrind is the fast instrument here (memcheck, still one
# run per build, dominates a corpus pass).
REPEATS = 3

_KEYS = ("Ir", "Bc", "Bi", "Dr", "Dw")

HERE = os.path.dirname(os.path.abspath(__file__))
# Under secrets/, which .gitignore already covers: these are regenerable.
_CTX_DIR = os.path.join(HERE, "secrets", "_ctx")


@contextlib.contextmanager
def context_dir(root=None):
    """
    A private directory for one build's contexts.

    Private per call, because the paths inside are reused across the two secret
    classes: a shared fixed location lets two concurrent measurements delete
    each other's files mid-run (observed -- a test raced a corpus run and the
    run died loading a secret the test had cleaned up).

    mkdtemp's suffix is a fixed width, so the directory name's LENGTH is the
    same every session even though its content is not. That matters: path
    length is the nuisance variable below, so it must not drift on its own.

    `root` overrides where those directories live. It defaults to this
    package's own secrets/_ctx, which is what leak_check wants but means an
    out-of-tree caller (prototypes/mlir_leak) would otherwise scatter its
    temporaries through a sibling prototype's tree. Callers should pass
    their own; keep the name a FIXED WIDTH under it, for the reason above.
    """
    ctx_root = root or _CTX_DIR
    os.makedirs(ctx_root, exist_ok=True)
    d = tempfile.mkdtemp(prefix="ctx", dir=ctx_root)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@contextlib.contextmanager
def _context(secret, i, ctx_dir):
    """
    Present `secret` inside `ctx_dir` at a path whose LENGTH varies with `i`.

    Path length is the nuisance variable we can move on purpose. Valgrind
    disables ASLR, so a run's memory layout is a deterministic function of its
    argv/env; lengthening the secret's path shifts everything allocated after
    it. Measured: the same weights (md5-identical) at two different paths give
    Ir 99,212 vs 99,707 -- a 495 swing from data that carries no information.

    Repeat `i` resolves to the same path for BOTH classes when they share a
    `ctx_dir`, so the pair is measured under one context and the diff is paired.
    """
    p = os.path.join(ctx_dir, "c" + "_" * (i * 8) + ".npy")
    shutil.copyfile(secret, p)
    try:
        yield p
    finally:
        try:
            os.unlink(p)
        except OSError:
            pass


def counts(model, secret, compile=False, repeats=REPEATS, ctx_dir=None):
    """
    `repeats` callgrind runs of one (model, secret, build), each in a distinct
    context.

    Repeating a run at a FIXED path is not a measurement of anything: it is
    bit-identical every time (observed: spread 0 across 16/16 runs), so its
    spread is 0 and any dIr looks significant. The reproducibility that matters
    is across contexts, so that is what a repeat varies.

    Pass `ctx_dir` to measure another class against the SAME contexts; omit it
    for a standalone spread measurement.
    """
    with contextlib.ExitStack() as stack:
        d = ctx_dir or stack.enter_context(context_dir())
        rows = []
        for i in range(repeats):
            with _context(secret, i, d) as p:
                rows.append(I.callgrind_count(model, p, compile=compile))
        return rows


def _measure_build(model, zero, rand, compile, repeats=REPEATS):
    # One dir for both classes: repeat i must be the SAME context for each, or
    # the "paired" diff below is just two unrelated measurements subtracted.
    with context_dir() as d:
        rows_zero = counts(model, zero, compile=compile, repeats=repeats, ctx_dir=d)
        rows_rand = counts(model, rand, compile=compile, repeats=repeats, ctx_dir=d)

    # Taint only needs the random secret; a dependence there is a dependence.
    # No floor applies: it reports a dependence, not a magnitude.
    taint = I.memcheck_taint(model, rand, compile=compile)

    # Floor+stability+paired-diff decision math is shared with any other
    # build axis via differential.py -- see its docstring. Only "Ir"/"Bc" can
    # make a build distinguishable here; the rest of _KEYS is summarized for
    # display only (cg_zero/cg_rand), matching the original scope exactly.
    v = D.compute_verdict_from_rows(rows_zero, rows_rand, _KEYS, ("Ir", "Bc"), taint)
    return {
        "cg_zero": v["med_zero"],
        "cg_rand": v["med_rand"],
        "ir_diff": v["diffs"]["Ir"],
        "bc_diff": v["diffs"]["Bc"],
        "ir_floor": v["floors"]["Ir"],
        "bc_floor": v["floors"]["Bc"],
        "ir_pairs": v["pairs"]["Ir"],
        "bc_pairs": v["pairs"]["Bc"],
        "ir_stable": v["stables"]["Ir"],
        "bc_stable": v["stables"]["Bc"],
        "repeats": repeats,
        "counts_distinguish": v["counts_distinguish"],
        "taint": v["taint"],
        "distinguishable": v["distinguishable"],
    }


def analyze(model, zero, rand, repeats=REPEATS):
    eager = _measure_build(model, zero, rand, compile=False, repeats=repeats)
    comp = _measure_build(model, zero, rand, compile=True, repeats=repeats)
    verdict = D.verdict_two_builds(eager["distinguishable"], comp["distinguishable"])
    return {"model": model, "eager": eager, "compiled": comp, "verdict": verdict}
