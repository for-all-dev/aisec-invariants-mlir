#!/usr/bin/env python3
"""The single normative ModelStatus blocker-cardinality collapse.

Three harness checkers used to implement step 11(b) of the aggregation
algorithm independently and disagreed with each other:

  * tools/check_rev4_high_value_fixtures.py implemented it correctly;
  * tools/artifact_bundle.py kept only the last unavailable row's reason and
    then demanded `Unknown(that reason)` even when several distinct reasons
    were open;
  * c/check_harness.py accepted any nonempty subset of the row reasons, which
    both admits a narrower answer than the rule allows and rejects the answer
    the rule mandates (``OpenModelObligations`` is never itself a row reason).

The rule has exactly one source of truth, quoted verbatim:

  SPS_Rev4_Normative_Specification.md:4192-4196 -- "otherwise, if
  `Blockers={r}`, return `Unknown(r)`, and if it contains multiple reasons
  return `Unknown({"reasonClassId":"OpenModelObligations"})`, preserving the
  full deterministically ordered blocker records only in the run-diagnostic
  restricted evidence bound to the final public report".

  SPS_Rev4_LLVM_Normal_Form_and_Conformance_Profile.md:2908-2910 -- "If
  exactly one blocker remains, `ModelStatus.Unknown` carries that class. If
  two or more remain, it carries `OpenModelObligations`; the complete
  canonical blocker set remains restricted. Empty blockers yield `Proved`."

Cardinality is counted over DISTINCT reason classes: several rows blocked for
the same reason leave one blocker, and the public tag stays that class.

This module computes a harness *expectation*. It never computes an authoritative
`ModelStatus`: nothing here parses a frozen artifact, establishes `NFConforms`,
runs a solver, or replays a witness. See contracts/FIXTURE_TIERS.md.
"""

from __future__ import annotations

OPEN_MODEL_OBLIGATIONS = "OpenModelObligations"


def collapse_blockers(reasons: object) -> str | None:
    """Return the single public reason class for a set of open blockers.

    ``None`` means no blocker remains (the caller may expect ``Proved``).
    Accepts any iterable of reason-class id strings; duplicates collapse.
    """
    distinct = {str(reason) for reason in (reasons or ())}
    if not distinct:
        return None
    if len(distinct) == 1:
        return next(iter(distinct))
    return OPEN_MODEL_OBLIGATIONS


def expected_model_status(
    *,
    accepted_bad_replay: bool,
    blockers: object,
    receipt_matcher: dict[str, object] | None = None,
    unknown_key: str = "args",
) -> dict[str, object]:
    """Build the expected ModelStatus matcher under the strict step-11 priority.

    Priority is (a) replayed counterexample, then (b) the blocker collapse, then
    (c) Proved -- spec:4185-4200. A counterexample outranks an open blocker, so
    `blockers` is deliberately not consulted in that branch.

    `unknown_key` selects the positional-argument spelling the calling checker
    already uses for its `Unknown` matcher (`args` everywhere today).
    """
    if accepted_bad_replay:
        matcher: dict[str, object] = {"tag": "Counterexample"}
        if receipt_matcher is not None:
            matcher["receipt_matcher"] = receipt_matcher
        return matcher
    reason = collapse_blockers(blockers)
    if reason is None:
        return {"tag": "Proved"}
    return {"tag": "Unknown", unknown_key: [{"reasonClassId": reason}]}


def describe(reasons: object) -> str:
    """Human-readable rendering of the collapse, for checker diagnostics."""
    distinct = sorted({str(reason) for reason in (reasons or ())})
    collapsed = collapse_blockers(distinct)
    if collapsed is None:
        return "0 blockers -> Proved"
    if len(distinct) == 1:
        return f"1 blocker {distinct[0]} -> Unknown({distinct[0]})"
    return (
        f"{len(distinct)} distinct blockers {distinct} -> "
        f"Unknown({OPEN_MODEL_OBLIGATIONS})"
    )


def _self_test() -> None:
    """Print the collapse over a fixed table so a lit test can pin it."""
    print(describe([]))
    print(describe(["SolverTimeout"]))
    print("duplicates collapse: " + describe(["SolverTimeout", "SolverTimeout"]))
    print(describe(["SolverTimeout", "PossibleUB"]))
    print(describe(["SolverTimeout", "PossibleUB", "PlacementMismatch"]))
    counterexample = expected_model_status(
        accepted_bad_replay=True, blockers=["SolverTimeout", "PossibleUB"]
    )
    if counterexample != {"tag": "Counterexample"}:
        raise SystemExit(f"counterexample priority broken: {counterexample!r}")
    print("counterexample outranks 2 open blockers -> Counterexample")


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["--self-test"]:
        _self_test()
    else:
        raise SystemExit("usage: sps_aggregation.py --self-test")
