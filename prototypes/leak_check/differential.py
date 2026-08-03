"""
Generalized differential non-interference decision math.

`noninterference.py` established the method for exactly two builds (eager,
compiled): context-varying paired counts, a floor (how far a count moves from
measurement context alone) and a stability guard (the paired diff must agree
across contexts), taint as the channel needing no magnitude difference at
all, and a same-shaped verdict from two builds' `distinguishable` bits. See
its module docstring for the full rationale and PRINCIPLES references.

This module factors the pure decision math (everything after "rows have
already been sampled") out of `noninterference._measure_build` so any other
build axis can reuse the identical recipe instead of re-deriving a weaker
version of it. `noninterference.py` itself is unchanged in behavior --
`_measure_build` now computes its legacy return shape by calling
`compute_verdict_from_rows` -- and stays the 2-build (eager/compiled)
instantiation. `prototypes/mlir_leak/run_mlir.py` is the N-build
instantiation (MLIR-lowering-pipeline x LLVM -O level), and reuses
`noninterference.context_dir`/`noninterference._context` directly for the
sampling side rather than re-deriving the context-varying nuisance knob.
"""

import statistics


def _spread(values):
    return max(values) - min(values)


def _summarize(rows, keys):
    keys = [k for k in keys if k in rows[0]]
    med = {k: int(statistics.median(r[k] for r in rows)) for k in keys}
    sp = {k: _spread([r[k] for r in rows]) for k in keys}
    return med, sp


def _paired(rows_zero, rows_rand, key):
    # strict=: pairing is only meaningful if both classes saw the same
    # contexts (see noninterference._paired for the full rationale).
    return [b[key] - a[key] for a, b in zip(rows_zero, rows_rand, strict=True)]


def compute_verdict_from_rows(rows_zero, rows_rand, summary_keys, decision_keys, taint):
    """
    Pure floor+stability+paired-diff decision math, generalized out of
    `noninterference._measure_build`.

    `rows_zero`/`rows_rand` are per-context measurement dicts already sampled
    at shared contexts (by `noninterference.counts` or an equivalent sampler
    for another build kind). `summary_keys` are reported as median/spread only
    (e.g. counters an instrument happens to emit); `decision_keys` are the
    subset a diff on any of which can make the build `distinguishable`
    (`noninterference.py` uses exactly `("Ir", "Bc")` -- widening this set
    changes what counts as a leak, so callers must choose it deliberately,
    not default to "every key present"). `taint` is the pre-computed
    `{"leak": bool, ...}` result for this build.
    """
    med_zero, spread_zero = _summarize(rows_zero, summary_keys)
    med_rand, spread_rand = _summarize(rows_rand, summary_keys)

    diffs, floors, stables, pairs = {}, {}, {}, {}
    for k in decision_keys:
        p = _paired(rows_zero, rows_rand, k)
        pairs[k] = p
        diffs[k] = int(statistics.median(p))
        floors[k] = max(spread_zero[k], spread_rand[k])
        stables[k] = _spread(p) <= floors[k]

    counts_distinguish = any(abs(diffs[k]) > floors[k] and stables[k] for k in decision_keys)
    distinguishable = counts_distinguish or taint["leak"]
    return {
        "med_zero": med_zero,
        "med_rand": med_rand,
        "diffs": diffs,
        "floors": floors,
        "stables": stables,
        "pairs": pairs,
        "counts_distinguish": counts_distinguish,
        "taint": taint,
        "distinguishable": distinguishable,
    }


def sample_over_contexts(sample_fn, secret, repeats, ctx_dir, context_fn):
    """
    `repeats` calls to `sample_fn(path)`, each at a distinct context produced
    by `context_fn(secret, i, ctx_dir)` (pass `noninterference._context` to
    reuse the exact same path-length nuisance knob `noninterference.py`
    calibrates against). For builds that already own a context-sampling loop
    with its own monkeypatch seam (`noninterference.counts`), call that
    directly instead -- this helper is for NEW build kinds (e.g. mlir_leak's
    compiled-kernel measurement) that don't have one yet.
    """
    rows = []
    for i in range(repeats):
        with context_fn(secret, i, ctx_dir) as p:
            rows.append(sample_fn(p))
    return rows


def verdict_two_builds(baseline_leak, other_leak):
    """
    `noninterference.py`'s authored/compiler-introduced/compiler-removed/
    oblivious quadrant, as a pure function of two `distinguishable` booleans
    (baseline = eager, other = compiled).
    """
    if baseline_leak and other_leak:
        return "authored"
    if other_leak and not baseline_leak:
        return "compiler-introduced"
    if baseline_leak and not other_leak:
        return "compiler-removed"
    return "oblivious"


def verdict_relative_to_baseline(baseline_leak, other_leak):
    """
    N-build generalization of `verdict_two_builds` for axes with no inherent
    eager/compiled meaning (e.g. mlir_leak's MLIR-lowering-pipeline x LLVM -O
    sweep): verdict of `other` relative to a chosen `baseline` build. Same
    four cases, renamed to not presuppose a compiler/source pair.
    """
    if baseline_leak and other_leak:
        return "leak-present-in-baseline"
    if other_leak and not baseline_leak:
        return "introduced-relative-to-baseline"
    if baseline_leak and not other_leak:
        return "removed-relative-to-baseline"
    return "oblivious"
