"""
Layer C — validate a leakage contract against the real silicon.

Layers A/B prove a program satisfies a *contract* (``[ct]`` / ``[cache-line]``)
in a solver's model of the machine. But the model is an assumption: the CPU may
leak MORE than the contract admits (a microcode assist, a data-dependent
prefetch, speculation). Layer C closes that trust gap the way Revizor / Scam-V
do — relational testing on the actual chip — but expressed through the SAME
information estimate as layer D: run the kernel on real silicon, estimate the
bits the timing leaks, and compare to what the contract ALLOWS.

The contract's allowance, in bits:

  - A contract verdict of ``secure`` claims the observable (here, wall-clock
    timing) carries **0 bits** of the secret. Any measured ``I(S;T)`` above the
    harness floor therefore REFUTES the contract on this CPU.
  - A contract verdict of ``insecure`` already predicts leakage; the measurement
    either CONFIRMS it or shows it is not exploitable at this config point (the
    contract was conservative — e.g. a byte-level leak that stays in one cache
    line, or a var-latency op the silicon happens to run in fixed time).

The headline case is ``d_denormal``: A (incl. its var-latency features) and B
both return ``secure`` — no secret-dependent branch, address, or integer mul/div
— yet the measured timing leaks ~1 bit/query because subnormal operands take a
microcode assist that binsec's instruction semantics do not model. C reports
that as a CONTRACT VIOLATION, quantified: the silicon leaks N bits the model
promised were 0. That is precisely the ``[ct]``-vs-silicon trust gap layer B
flags as out of its own scope.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .estimate import LeakEstimate


@dataclass
class SiliconVerdict:
    kernel: str
    contract: str  # the contract label being validated, e.g. "[ct]" or "[cache-line]"
    contract_verdict: str  # "secure" | "insecure": what A/B concluded in the model
    allowed_bits: float  # bits the contract permits (0.0 when it claims secure)
    measured_bits: float  # debiased I(S;T) from silicon
    p_value: float
    status: str  # see below
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


# status values
CONSISTENT = "consistent"  # secure contract, silicon shows no channel — model holds
VIOLATED = "contract-violated"  # secure contract, silicon leaks anyway — model refuted
CONFIRMED = "confirmed"  # insecure contract, silicon leaks as predicted
NOT_EXPLOITABLE = "not-exploitable-here"  # insecure contract, silicon shows no channel


def validate_against_silicon(
    est: LeakEstimate,
    *,
    contract: str,
    contract_verdict: str,
    allowed_bits: float | None = None,
) -> SiliconVerdict:
    """Compare a measured leak estimate to what the contract allows."""
    cv = contract_verdict.lower()
    leaks = est.verdict == "leak"
    # A "secure" contract allows 0 bits; an explicit allowance overrides.
    allowed = (0.0 if cv == "secure" else est.max_bits) if allowed_bits is None else allowed_bits

    if cv == "secure":
        if leaks and est.mi_bits > allowed:
            status = VIOLATED
            detail = (
                f"{contract} contract claims {allowed:.2f} bits but silicon leaks "
                f"~{est.mi_bits:.3f} bits/query (perm p={est.mi_p_value:.2g}, "
                f"dudect t={est.t_stat:.1f}) — MODEL REFUTED on this CPU"
            )
        else:
            status = CONSISTENT
            detail = (
                f"{contract} contract holds: silicon leaks {est.mi_bits:.3f} bits "
                f"(≤ allowed {allowed:.2f}), no channel above floor"
            )
    else:  # contract already says insecure
        if leaks:
            status = CONFIRMED
            detail = (
                f"{contract} contract predicts a leak; silicon confirms "
                f"~{est.mi_bits:.3f} bits/query (dudect t={est.t_stat:.1f})"
            )
        else:
            status = NOT_EXPLOITABLE
            detail = (
                f"{contract} contract is insecure but silicon shows no channel "
                f"({est.mi_bits:.3f} bits) — conservative at this config point"
            )

    return SiliconVerdict(
        kernel=est.kernel,
        contract=contract,
        contract_verdict=cv,
        allowed_bits=allowed,
        measured_bits=est.mi_bits,
        p_value=est.mi_p_value,
        status=status,
        detail=detail,
    )
