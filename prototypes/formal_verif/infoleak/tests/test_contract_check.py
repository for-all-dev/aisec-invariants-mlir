"""Layer-C logic tests: measured bits vs. contract allowance (no CPU needed)."""

from infoleak.contract_check import (
    CONFIRMED,
    CONSISTENT,
    NOT_EXPLOITABLE,
    VIOLATED,
    validate_against_silicon,
)
from infoleak.estimate import LeakEstimate


def _est(mi_bits: float, verdict: str, kernel: str = "k") -> LeakEstimate:
    return LeakEstimate(
        kernel=kernel,
        n_samples=20000,
        class_counts={0: 10000, 1: 10000},
        mi_bits=mi_bits,
        mi_raw_bits=mi_bits + 0.001,
        mi_null_mean=0.001,
        mi_null_std=0.0005,
        mi_p_value=0.003 if verdict == "leak" else 0.4,
        max_bits=1.0,
        t_stat=-2000.0 if verdict == "leak" else 0.3,
        t_leaks=verdict == "leak",
        median_cycles={0: 100.0, 1: 100.0},
        bins=20,
        permutations=300,
        verdict=verdict,
        detail="",
    )


def test_secure_contract_no_leak_is_consistent():
    v = validate_against_silicon(
        _est(0.0, "no-detectable-leak"), contract="[ct]", contract_verdict="secure"
    )
    assert v.status == CONSISTENT
    assert v.allowed_bits == 0.0


def test_secure_contract_but_silicon_leaks_is_violation():
    # the d_denormal headline: A/B say secure, silicon leaks anyway.
    v = validate_against_silicon(_est(0.99, "leak"), contract="[ct]", contract_verdict="secure")
    assert v.status == VIOLATED
    assert v.measured_bits == 0.99


def test_insecure_contract_leak_is_confirmed():
    v = validate_against_silicon(_est(0.99, "leak"), contract="[ct]", contract_verdict="insecure")
    assert v.status == CONFIRMED


def test_insecure_contract_no_measured_leak_is_not_exploitable():
    v = validate_against_silicon(
        _est(0.0, "no-detectable-leak"), contract="[ct]", contract_verdict="insecure"
    )
    assert v.status == NOT_EXPLOITABLE
