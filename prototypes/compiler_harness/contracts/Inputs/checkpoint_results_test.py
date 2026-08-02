#!/usr/bin/env python3
"""Focused assertions for the minimal Snapshot V3 final-result view."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FORMAT_ID = "SPS-Harness-Fixture-Final-Result-View-v2"

PROVED_CASES = frozenset(
    {
        "abi-alias/disjoint-control",
        "alloca-size/public-control",
        "breach-compressed-length/fixed",
        "ckks-release/fixed",
        "clangover-poly-frommsg/lowered-fixed",
        "clangover-poly-frommsg/source",
        "dynamic-kv-length/fixed",
        "explicit-error-oracle/fixed",
        "kyberslash1-poly-tomsg/fixed",
        "kyberslash2-compress/fixed",
        "launder-scan/folded-mask-p4-open",
        "launder-scan/model-clean-p4-open",
        "leftoverlocals-scratch/fixed",
        "precision-control/identical-successor",
        "precision-control/offset-disjoint",
        "precision-control/overwritten-slot",
        "precision-control/xor-cancellation",
        "redis-pool-reuse/fixed",
        "secret-embedding-index/fixed",
        "secret-logging-checkpoint/fixed",
        "wolfssl-3579-mul/target-constant-latency",
        "wolfssl-3579-mul/target-fixed",
        "wolfssl-3580-mask/source",
        "wolfssl-3580-mask/target-fixed",
        "wrong-host-fhe-reveal/fixed",
        "wrong-party-plaintext/fixed",
    }
)

COUNTEREXAMPLE_CASES = {
    "abi-alias/explicit-same-actual-bad": "public-output-payload-mismatch",
    "abi-alias/mayalias-overlap-bad": "public-output-payload-mismatch",
    "audience-mismatch/bad": "bob-visible-output-while-release-obligation-active",
    "breach-compressed-length/bad": "public-wire-length-mismatch",
    "ckks-release/bad": "raw-unauthorized-public-release-mismatch",
    "clangover-poly-frommsg/lowered-bad": "world-control-timing-mismatch",
    "dynamic-kv-length/bad": "public-counts-mismatch",
    "explicit-error-oracle/bad": "public-error-detail-mismatch",
    "kyberslash1-poly-tomsg/bad": "timing-cost-mismatch",
    "kyberslash2-compress/bad": "timing-cost-mismatch",
    "leftoverlocals-scratch/bad": "next-tenant-output-mismatch",
    "loop-bounds/secret-trip-count-bad": "world-control-location-mismatch",
    "predecessor-choice/blockarg-bad": "public-output-block-argument-mismatch",
    "prefix-causal-release/bad": "pre-release-public-observation",
    "redis-pool-reuse/bad": "actor-b-return-payload-mismatch",
    "secret-embedding-index/bad": "address-trace-mismatch",
    "secret-logging-checkpoint/bad": "public-log-checkpoint-payload-mismatch",
    "wolfssl-3579-mul/target-bad": "helper-timing-cost-mismatch",
    "wolfssl-3580-mask/target-bad": "world-control-timing-mismatch",
    "wrong-host-fhe-reveal/bad": "unauthorized-server-output-mismatch",
    "wrong-party-plaintext/bad": "unauthorized-mailbox-output-mismatch",
}

UNKNOWN_CASES = {
    "abi-alias/missing-binding-unknown": "AliasBindingMismatch",
    "alloca-size/high-count-unknown": "AllocaSizeNotWorldStructural",
    "launder-scan/barrier-fixed": "UnsupportedOpcode",
    "loop-bounds/public-bound-exhausted-unknown": "LoopRemainder",
    "release-carrier/lost-bad": "ReleaseCarrierMismatch",
    "release-carrier/marker-only-bad": "ReleaseCarrierMismatch",
    "release-carrier/pinned-control": "ReleaseCarrierMismatch",
    "wolfssl-3579-mul/source": "OpenModelObligations",
    "wolfssl-3579-mul/target-unknown": "OpenModelObligations",
}

CANDIDATE_CASES = frozenset(
    {
        "abi-alias/disjoint-control",
        "abi-alias/mayalias-overlap-bad",
        "abi-alias/missing-binding-unknown",
        "alloca-size/high-count-unknown",
        "alloca-size/public-control",
        "audience-mismatch/bad",
        "launder-scan/model-clean-p4-open",
        "loop-bounds/public-bound-exhausted-unknown",
        "loop-bounds/secret-trip-count-bad",
    }
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    assert isinstance(value, dict)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("view", type=Path)
    args = parser.parse_args()
    view = load_json(args.view)

    assert set(view) == {"format_id", "results", "summary"}
    assert view["format_id"] == FORMAT_ID
    assert view["summary"] == {
        "fixtures": 56,
        "expected_proved": 26,
        "expected_counterexample": 21,
        "expected_unknown": 9,
        "compared": 0,
    }

    rows = view["results"]
    assert isinstance(rows, list) and len(rows) == 56
    assert [row["case"] for row in rows] == sorted(row["case"] for row in rows)
    by_case = {row["case"]: row for row in rows}

    expected_cases = set(PROVED_CASES) | set(COUNTEREXAMPLE_CASES) | set(UNKNOWN_CASES)
    assert len(PROVED_CASES) == 26
    assert len(COUNTEREXAMPLE_CASES) == 21
    assert len(UNKNOWN_CASES) == 9
    assert expected_cases == set(by_case)

    for case, row in by_case.items():
        assert set(row) == {
            "case",
            "expected_final",
            "actual_final",
            "comparison",
            "checkpoint_result",
        }
        assert row["actual_final"] is None
        assert row["comparison"] == "NotCompared"
        assert row["checkpoint_result"] in {
            "NotObserved",
            "PartiallyObserved",
            "PassedV1",
            "FailedV1",
            "InvalidObservation",
        }
        final = row["expected_final"]
        assert final["deployment"] == "Open"
        assert final["policy"] == "Complete"
        assert isinstance(final["because"], str) and final["because"]
        events = final["events"]

        if case in PROVED_CASES:
            assert final["model"] == {"status": "Proved"}
            assert events
            assert not any(event.get("first_bad") for event in events)
        elif case in COUNTEREXAMPLE_CASES:
            assert final["model"] == {
                "status": "Counterexample",
                "bad_state": COUNTEREXAMPLE_CASES[case],
            }
            assert events
            assert sum(event.get("first_bad") is True for event in events) == 1
        else:
            assert final["model"] == {
                "status": "Unknown",
                "reason": UNKNOWN_CASES[case],
            }

        for event in events:
            assert set(event) <= {"kind", "field", "id", "first_bad"}
            assert {"kind", "field"} <= set(event)

        if case in CANDIDATE_CASES:
            assert final["reference"] == "candidate/expected-report.json"
        else:
            assert "reference" not in final

    print("minimal Snapshot V3 result view passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
