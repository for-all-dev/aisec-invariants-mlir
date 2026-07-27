"""
Calibration of the SHARED decision engine (differential.py) and of the one
place a consumer deliberately diverges from it.

test_count_confound.py pins the criterion as noninterference.py instantiates
it (eager vs compiled, decision on Ir/Bc). This file pins the engine itself,
including the part that is now reused by another prototype
(prototypes/mlir_leak), so a change there cannot silently alter either
consumer's meaning.

The decision-key set is the divergence worth pinning. It is a PARAMETER, and
the two consumers pass different values on purpose:

  noninterference.py : ("Ir", "Bc")        -- as its results were recorded
  mlir_leak          : ("Ir", "Bc", "Dw")  -- + the memory channel

Widening the set makes the criterion fire on strictly MORE cases, so it is
not a free choice: a Dw-only difference is a leak for mlir_leak and is not
one for leak_check. That is intended (mlir_leak's dynamic-shape liveness
finding -- a secret-sized buffer's Dw footprint surviving -O2 -- is a Dw-only
result, invisible on Ir/Bc), but it must be explicit and tested rather than
an accident of whoever edited last.
"""

import differential as D

_NI_KEYS = ("Ir", "Bc")
_MLIR_LEAK_KEYS = ("Ir", "Bc", "Dw")
_SUMMARY = ("Ir", "Bc", "Bi", "Dr", "Dw")

_CLEAN = {"leak": False, "reports": []}
_TAINTED = {"leak": True, "reports": ["dep"]}


def rows(*triples):
    """One (Ir, Bc, Dw) measurement per context."""
    return [dict(Ir=ir, Bc=bc, Dw=dw, Bi=0, Dr=0) for ir, bc, dw in triples]


# --- the deliberate divergence: a Dw-ONLY difference ------------------------


def _dw_only():
    # Ir and Bc identical in every context; only the memory-write count moves,
    # stably and far above its own context floor.
    zero = rows((100, 20, 1_000), (100, 20, 1_000), (100, 20, 1_000))
    rand = rows((100, 20, 5_000), (100, 20, 5_000), (100, 20, 5_000))
    return zero, rand


def test_dw_only_is_not_a_leak_under_leak_check_keys():
    zero, rand = _dw_only()
    v = D.compute_verdict_from_rows(zero, rand, _SUMMARY, _NI_KEYS, _CLEAN)
    assert not v["counts_distinguish"]
    assert not v["distinguishable"]


def test_dw_only_is_a_leak_under_mlir_leak_keys():
    zero, rand = _dw_only()
    v = D.compute_verdict_from_rows(zero, rand, _SUMMARY, _MLIR_LEAK_KEYS, _CLEAN)
    assert v["counts_distinguish"]
    assert v["distinguishable"]
    assert v["diffs"]["Dw"] == 4_000


def test_widening_keys_can_only_add_leaks_never_remove_them():
    # The direction of the divergence is the whole point: the wider set is
    # strictly more trigger-happy, so it can never call something oblivious
    # that the narrower set called a leak.
    zero = rows((100, 20, 1_000), (100, 20, 1_000), (100, 20, 1_000))
    rand = rows((900, 80, 1_000), (900, 80, 1_000), (900, 80, 1_000))
    narrow = D.compute_verdict_from_rows(zero, rand, _SUMMARY, _NI_KEYS, _CLEAN)
    wide = D.compute_verdict_from_rows(zero, rand, _SUMMARY, _MLIR_LEAK_KEYS, _CLEAN)
    assert narrow["distinguishable"] and wide["distinguishable"]


# --- the guards themselves, on the shared engine ---------------------------


def test_floor_suppresses_a_sub_floor_difference():
    # Stable, but smaller than what context alone does to each class.
    zero = rows((100_000, 400, 0), (101_000, 400, 0), (102_000, 400, 0))
    rand = rows((100_100, 400, 0), (101_100, 400, 0), (102_100, 400, 0))
    v = D.compute_verdict_from_rows(zero, rand, _SUMMARY, _NI_KEYS, _CLEAN)
    assert v["pairs"]["Ir"] == [100] * 3 and v["stables"]["Ir"]
    assert abs(v["diffs"]["Ir"]) <= v["floors"]["Ir"]
    assert not v["distinguishable"]


def test_instability_suppresses_a_large_difference():
    # Clears the floor on magnitude but does not reproduce across contexts.
    zero = rows((100_000, 400, 0), (101_000, 400, 0), (100_000, 400, 0))
    rand = rows((106_000, 400, 0), (105_000, 400, 0), (106_000, 400, 0))
    v = D.compute_verdict_from_rows(zero, rand, _SUMMARY, _NI_KEYS, _CLEAN)
    assert abs(v["diffs"]["Ir"]) > v["floors"]["Ir"]
    assert not v["stables"]["Ir"]
    assert not v["distinguishable"]


def test_taint_needs_no_magnitude():
    zero = rows((100, 20, 0), (100, 20, 0), (100, 20, 0))
    v = D.compute_verdict_from_rows(zero, zero, _SUMMARY, _NI_KEYS, _TAINTED)
    assert not v["counts_distinguish"]
    assert v["distinguishable"]


# --- verdict vocabularies ---------------------------------------------------


def test_two_build_verdict_quadrant():
    assert D.verdict_two_builds(True, True) == "authored"
    assert D.verdict_two_builds(False, True) == "compiler-introduced"
    assert D.verdict_two_builds(True, False) == "compiler-removed"
    assert D.verdict_two_builds(False, False) == "oblivious"


def test_baseline_relative_verdict_is_the_same_quadrant_renamed():
    assert D.verdict_relative_to_baseline(True, True) == "leak-present-in-baseline"
    assert D.verdict_relative_to_baseline(False, True) == "introduced-relative-to-baseline"
    assert D.verdict_relative_to_baseline(True, False) == "removed-relative-to-baseline"
    assert D.verdict_relative_to_baseline(False, False) == "oblivious"
