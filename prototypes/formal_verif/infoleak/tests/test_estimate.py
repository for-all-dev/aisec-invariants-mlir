"""Calibration tests for the information estimator (no binsec / no CPU needed).

These are the software analogue of the corpus's positive/negative controls: on
synthetic data with known ground truth the estimator must return ~0 bits when
the label is independent of the timing, and a large fraction of a bit when the
timing determines the label — and the permutation-null debias must cancel the
finite-sample bias in the independent case.
"""

import numpy as np

from infoleak.estimate import (
    _entropy_bits,
    _mi_bits_from_joint,
    estimate_leak,
)


def test_mi_of_independent_joint_is_zero():
    # class independent of bin => exact MI 0.
    joint = np.array([[10, 20, 30], [10, 20, 30]])
    assert _mi_bits_from_joint(joint) == 0.0


def test_mi_of_perfectly_dependent_joint_is_full_entropy():
    # class perfectly determines the bin => MI == H(S) == 1 bit for 2 balanced classes.
    joint = np.array([[50, 0], [0, 50]])
    assert abs(_mi_bits_from_joint(joint) - 1.0) < 1e-9


def test_entropy_two_balanced_classes_is_one_bit():
    assert abs(_entropy_bits(np.array([100, 100])) - 1.0) < 1e-9


def test_negative_control_no_leak():
    # Timing drawn from the SAME distribution regardless of class => no channel.
    rng = np.random.default_rng(1)
    n = 8000
    classes = rng.integers(0, 2, n)
    cycles = rng.normal(1000, 50, n)  # independent of `classes`
    est = estimate_leak(classes, cycles, kernel="synthetic_ct", permutations=200, seed=1)
    assert est.verdict == "no-detectable-leak"
    # the debias must cancel the plug-in bias to ~0, even though raw MI > 0.
    assert est.mi_bits < 0.02
    assert est.mi_raw_bits >= est.mi_bits  # raw is the biased-up one
    assert est.mi_p_value > 0.01


def test_positive_control_strong_leak():
    # Timing separated by class => the estimator must recover ~1 bit.
    rng = np.random.default_rng(2)
    n = 8000
    classes = rng.integers(0, 2, n)
    cycles = np.where(classes == 0, 1000, 5000) + rng.normal(0, 30, n)
    est = estimate_leak(classes, cycles, kernel="synthetic_leak", permutations=200, seed=2)
    assert est.verdict == "leak"
    assert est.mi_bits > 0.8
    assert est.mi_p_value < 0.01
    assert est.t_leaks  # dudect t should also fire


def test_partial_leak_between_zero_and_one_bit():
    # Overlapping-but-shifted distributions => a partial, sub-1-bit channel.
    rng = np.random.default_rng(3)
    n = 12000
    classes = rng.integers(0, 2, n)
    cycles = np.where(classes == 0, 1000, 1120) + rng.normal(0, 100, n)
    est = estimate_leak(classes, cycles, kernel="synthetic_partial", permutations=200, seed=3)
    assert est.verdict == "leak"
    assert 0.02 < est.mi_bits < 0.8  # some, but not all, of the bit
