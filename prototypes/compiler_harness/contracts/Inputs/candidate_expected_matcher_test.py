#!/usr/bin/env python3
"""Focused contract tests for tools/candidate_expected_matcher.py."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


HARNESS = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(HARNESS / "tools"))

import candidate_expected_matcher as matcher  # noqa: E402
import sps_interfaces  # noqa: E402


VECTORS = HARNESS / "contracts/vendor/sps-rev4.1/vectors/canonical-valid"
OPEN_DEPLOYMENT = {
    "tag": "Open",
    "args": [{"tag": "P4EvidenceProfileUnavailable"}],
}
COMPLETE_POLICY = {"tag": "Complete"}
COALITION = ["principal.fixture"]
ENTRY = "entry_main"


def discharged_outcome() -> dict[str, Any]:
    return {
        "tag": "ConstructedResultMatcherV2",
        "raw_solver_result": "UNSAT",
        "query_disposition": {"tag": "Discharged"},
    }


def no_replay() -> dict[str, str]:
    return {"tag": "NotApplicableV2"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_write(path: Path, value: object) -> None:
    path.write_bytes(sps_interfaces.canonical_bytes(value))


def materialize(root: Path, decision: dict[str, Any]) -> tuple[Path, Path]:
    root.mkdir()
    bundle = root / "materialized"
    bundle.mkdir()
    evidence = decision["identityEvidence"]
    manifest = json.loads((VECTORS / "nf-manifest.v2.json").read_text())
    values = {
        "artifact-identity.sps.json": evidence["artifactIdentity"],
        "identity-evidence.sps.json": evidence,
        "sps-manifest.sps.json": manifest,
        "proof-configuration.sps.json": evidence["proofConfiguration"],
        "aggregation-input.sps.json": decision["input"],
    }
    for name, value in values.items():
        canonical_write(bundle / name, value)
    (bundle / "artifact.bc").write_bytes(
        bytes.fromhex(evidence["canonicalBitcode"]["exactBytes"])
    )
    report = root / "report.sps.json"
    canonical_write(report, decision["runReport"])
    return bundle, report


def candidate_expectation(
    root: Path, expected: dict[str, Any], *, candidate_bytes: bytes = b"old-candidate"
) -> Path:
    root.mkdir()
    (root / "artifact.bc").write_bytes(candidate_bytes)
    bitcode_digest = digest(candidate_bytes)
    sidecar = {
        "format_id": matcher.EXPECTED_FORMAT_ID,
        "fixture_tier": {"tag": "CandidateOnly"},
        "claimable_from_checked_in_pair": False,
        "required_checker_feature": "sps-verifier",
        "current_harness_status": {
            "tag": "PendingV2",
            "reasons": ["contract-test-only"],
        },
        "expected": expected,
        "candidate_bitcode_sha256": bitcode_digest,
    }
    sidecar_raw = (json.dumps(sidecar, indent=2) + "\n").encode()
    sidecar_path = root / "expected-report.json"
    sidecar_path.write_bytes(sidecar_raw)
    artifact = {
        "format_id": matcher.ARTIFACT_FORMAT_ID,
        "artifact_role": "checked-in-bitcode-candidate",
        "fixture_tier": {"tag": "CandidateOnly"},
        "claimable": False,
        "candidate_bitcode_sha256": bitcode_digest,
        "candidate_sidecar_sha256": {
            "expected-report.json": digest(sidecar_raw),
        },
    }
    (root / "artifact.json").write_text(json.dumps(artifact))
    return sidecar_path


def expectation(
    *,
    model: dict[str, Any],
    query_outcome: dict[str, Any],
    replay: dict[str, Any],
    empty_query_outcome: dict[str, Any] | None = None,
    empty_replay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "entry": ENTRY,
        "audit_all_expectations": [
            {
                "coalition": [],
                "query_outcome": empty_query_outcome or discharged_outcome(),
                "replay_expectation": empty_replay or no_replay(),
            },
            {
                "coalition": COALITION,
                "query_outcome": query_outcome,
                "replay_expectation": replay,
            }
        ],
        "expected_model_status": model,
        "expected_deployment_status": OPEN_DEPLOYMENT,
        "expected_policy_review_status": COMPLETE_POLICY,
    }


def proved_expectation() -> dict[str, Any]:
    return expectation(
        model={"tag": "Proved"},
        query_outcome=discharged_outcome(),
        replay=no_replay(),
    )


def unknown_decision() -> tuple[dict[str, Any], dict[str, Any]]:
    decision = json.loads((VECTORS / "proved-decision.v2.json").read_text())
    reason = {"reasonClassId": "AliasBindingMismatch"}
    row = decision["runReport"]["report"]["queryResults"][1]
    protected = row["outcome"]["args"][0]["protectedEvidence"]
    row["outcome"] = {
        "tag": "NotConstructedV2",
        "reason": reason,
        "protectedEvidence": protected,
    }
    decision["input"]["blockers"] = [
        {
            "formatId": "SPS-Blocker-Record-v2",
            "scope": "ProofCompletion",
            "phaseOrdinal": 2,
            "scheduleOrdinal": {"tag": "Some", "value": 1},
            "reason": {"tag": "ModelBlocker", "reason": reason},
            "restrictedDetailDigest": "0" * 64,
        }
    ]
    decision["input"]["allRequiredGatesClosed"] = False
    decision["runReport"]["report"]["modelStatus"] = {
        "tag": "Unknown",
        "args": [reason],
    }
    expected = expectation(
        model={"tag": "Unknown", "args": [reason]},
        query_outcome={"tag": "NotConstructedResultMatcherV2", "reason": reason},
        replay={"tag": "NotAvailableV2", "reason": reason},
    )
    return decision, expected


def counterexample_expectation() -> dict[str, Any]:
    return expectation(
        model={
            "tag": "Counterexample",
            "receipt_matcher": {"tag": "FreshProtectedReceiptMatcherV2"},
        },
        query_outcome=discharged_outcome(),
        replay=no_replay(),
        empty_query_outcome={
            "tag": "ConstructedResultMatcherV2",
            "raw_solver_result": "SAT",
            "query_disposition": {"tag": "CandidateOnly"},
        },
        empty_replay={
            "tag": "AcceptedBadStateRequiredV2",
            "bad_state_class": "public-output-payload-mismatch",
        },
    )


def tracked_candidate_hashes() -> dict[Path, str]:
    paths = sorted(HARNESS.glob("fixtures/*/*/candidate/*"))
    return {path: digest(path.read_bytes()) for path in paths if path.is_file()}


def main() -> None:
    before = tracked_candidate_hashes()
    checked = 0
    for sidecar in sorted(
        HARNESS.glob("fixtures/*/*/candidate/expected-report.json")
    ):
        matcher.load_candidate_expectation(sidecar)
        checked += 1
    assert checked == 8
    assert tracked_candidate_hashes() == before

    build_root = Path(os.environ["LIT_BUILD_ROOT"])
    with tempfile.TemporaryDirectory(dir=build_root) as temporary:
        root = Path(temporary)

        proved = json.loads((VECTORS / "proved-decision.v2.json").read_text())
        proved_bundle, proved_report = materialize(root / "proved-run", proved)
        proved_sidecar = candidate_expectation(
            root / "proved-candidate", proved_expectation()
        )
        # The quarantined capture authenticates the sidecar but is not falsely
        # equated with the conformant materialized recapture.
        assert (proved_sidecar.parent / "artifact.bc").read_bytes() != (
            proved_bundle / "artifact.bc"
        ).read_bytes()
        proved_result = matcher.match_candidate_expected_run(
            proved_sidecar, proved_bundle, proved_report
        )
        assert proved_result.matched

        unknown, unknown_expected = unknown_decision()
        unknown_bundle, unknown_report = materialize(root / "unknown-run", unknown)
        unknown_sidecar = candidate_expectation(
            root / "unknown-candidate", unknown_expected
        )
        unknown_result = matcher.match_candidate_expected_run(
            unknown_sidecar, unknown_bundle, unknown_report
        )
        assert unknown_result.matched

        counterexample = json.loads(
            (VECTORS / "aggregation-decision.v2.json").read_text()
        )
        # The complete coalition closure adds the empty coalition ahead of the
        # authored maximum. Keep one accepted bad replay at the empty row and
        # make the other AuditAll row clean so the focused matcher test models
        # the one-replay aggregation contract exactly.
        other_audit = counterexample["runReport"]["report"]["queryResults"][1]
        other_result = other_audit["outcome"]["args"][0]
        other_result["rawSolverResult"] = "UNSAT"
        other_result["queryDisposition"] = {"tag": "Discharged"}
        counter_bundle, counter_report = materialize(
            root / "counterexample-run", counterexample
        )
        counter_sidecar = candidate_expectation(
            root / "counterexample-candidate", counterexample_expectation()
        )
        counter_result = matcher.match_candidate_expected_run(
            counter_sidecar, counter_bundle, counter_report
        )
        assert counter_result.observable_fields_match
        assert not counter_result.matched
        assert len(counter_result.unresolved) == 1
        assert "bad_state_class" in counter_result.unresolved[0]

        wrong = copy.deepcopy(proved_expectation())
        wrong["expected_deployment_status"] = {"tag": "Closed"}
        wrong_sidecar = candidate_expectation(root / "wrong-candidate", wrong)
        wrong_result = matcher.match_candidate_expected_run(
            wrong_sidecar, proved_bundle, proved_report
        )
        assert not wrong_result.matched
        assert any("DeploymentStatus" in item for item in wrong_result.mismatches)

        stale_sidecar = candidate_expectation(
            root / "stale-candidate", proved_expectation()
        )
        stale_sidecar.write_bytes(stale_sidecar.read_bytes() + b"\n")
        try:
            matcher.load_candidate_expectation(stale_sidecar)
        except matcher.CandidateExpectedMatcherError as error:
            assert "envelope" in str(error)
        else:
            raise AssertionError("stale sidecar digest was accepted")

    print(f"authenticated {checked} checked-in candidate expectation envelopes")
    print("matched Proved and Unknown materialized reports")
    print("Counterexample bad_state_class failed closed as unresolved")
    print("rejected axis mismatch and stale sidecar digest")


if __name__ == "__main__":
    main()
