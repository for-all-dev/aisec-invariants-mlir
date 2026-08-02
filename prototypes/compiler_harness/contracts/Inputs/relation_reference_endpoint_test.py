#!/usr/bin/env python3
"""Canonical endpoint, authority, and cross-case binding refusals."""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    build = Path(sys.argv[2]).resolve()
    build.mkdir(parents=True, exist_ok=True)
    os.environ["LIT_BUILD_ROOT"] = str(build)
    sys.path.insert(0, str(root / "tools"))
    import checkpoint_model
    import checkpoint_runner

    reference = (
        root
        / "contracts"
        / "vendor"
        / "sps-reference-rev4"
        / "reference"
    )
    sys.path.insert(0, str(reference))
    from sps_ref import canonical, evidence

    case = root / "fixtures" / "precision-control" / "identical-successor"
    fixture_path = case / "relation-reference" / "fixture.json"
    binding_path = case / "relation-reference" / "binding.json"
    fixture = canonical.load_json_bytes(fixture_path.read_bytes())
    binding = canonical.load_json_bytes(binding_path.read_bytes())
    result = evidence.run_relation_fixture(
        fixture,
        binding,
        fixture_path=fixture_path,
        binding_path=binding_path,
    )
    raw = evidence.canonical_relation_result_bytes(result)
    snapshot = checkpoint_model.load_snapshot(case / "snapshot.yaml", root)
    pipeline = snapshot.pipelines["relation-reference"]
    facts, payload, mismatches = checkpoint_runner._validate_endpoint(
        snapshot, pipeline, raw
    )
    assert not mismatches
    assert facts == evidence.project_relation_result(result)
    assert payload is not None
    payload_path = build / payload["path"]
    assert payload_path.read_bytes() == raw
    assert checkpoint_model.byte_digest(raw) == payload["sha256"]

    def rejected(
        rejected_snapshot: object,
        rejected_pipeline: object,
        endpoint: bytes,
        expected: str,
    ) -> None:
        try:
            checkpoint_runner._validate_endpoint(
                rejected_snapshot, rejected_pipeline, endpoint
            )
        except checkpoint_runner.RunnerError as error:
            assert expected in str(error), (expected, str(error))
        else:
            raise AssertionError(f"relation endpoint mutation accepted: {expected}")

    rejected(snapshot, pipeline, raw + b"\n", "not canonical JSON")

    authoritative = copy.deepcopy(result)
    authoritative["modelStatus"] = "Proved"
    rejected(
        snapshot,
        pipeline,
        canonical.canonical_bytes(authoritative),
        "forbidden authoritative field",
    )

    wrong_profile = copy.deepcopy(result)
    wrong_profile["profileBinding"]["canonicalProfileDigest"] = "0" * 64
    preimage = dict(wrong_profile)
    preimage.pop("canonicalResultDigest")
    wrong_profile["canonicalResultDigest"] = canonical.canonical_digest(preimage)
    rejected(
        snapshot,
        pipeline,
        canonical.canonical_bytes(wrong_profile),
        "profile binding differs",
    )

    wrong_check = copy.deepcopy(result)
    wrong_check["artifactIntegrity"][0]["checkId"] = "NormativeModelStatus"
    preimage = dict(wrong_check)
    preimage.pop("canonicalResultDigest")
    wrong_check["canonicalResultDigest"] = canonical.canonical_digest(preimage)
    rejected(
        snapshot,
        pipeline,
        canonical.canonical_bytes(wrong_check),
        "integrity evidence differs",
    )

    other_case = root / "fixtures" / "precision-control" / "xor-cancellation"
    other_snapshot = checkpoint_model.load_snapshot(other_case / "snapshot.yaml", root)
    rejected(
        other_snapshot,
        other_snapshot.pipelines["relation-reference"],
        raw,
        "differs from its fixture context",
    )

    print("relation-reference endpoint refusals passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
