#!/usr/bin/env python3
"""Canonical endpoint, authority, and cross-case binding refusals."""

from __future__ import annotations

import copy
import hashlib
import os
import shutil
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

    # SAT reference endpoints select a case-local synthetic pair.  Exercise the
    # checkpoint endpoint against a private case copy so missing/stale bytes and
    # a digest-updated but semantically invalid pair all fail closed through the
    # contextual reference API.
    bad_source = root / "fixtures" / "precision-control" / "different-successor-bad"
    contextual_root = build / "pair-context"
    bad_case = contextual_root / "fixtures" / "precision-control" / "different-successor-bad"
    if contextual_root.exists():
        shutil.rmtree(contextual_root)
    bad_case.parent.mkdir(parents=True)
    shutil.copytree(bad_source, bad_case)
    bad_fixture_path = bad_case / "relation-reference" / "fixture.json"
    bad_binding_path = bad_case / "relation-reference" / "binding.json"
    bad_pair_path = bad_case / "counterexample-pair.yaml"
    bad_fixture = canonical.load_json_bytes(bad_fixture_path.read_bytes())
    bad_binding = canonical.load_json_bytes(bad_binding_path.read_bytes())
    bad_result = evidence.run_relation_fixture(
        bad_fixture,
        bad_binding,
        fixture_path=bad_fixture_path,
        binding_path=bad_binding_path,
    )
    bad_raw = evidence.canonical_relation_result_bytes(bad_result)
    bad_snapshot = checkpoint_model.load_snapshot(bad_case / "snapshot.yaml", contextual_root)
    bad_pipeline = bad_snapshot.pipelines["relation-reference"]
    bad_facts, _, bad_mismatches = checkpoint_runner._validate_endpoint(
        bad_snapshot, bad_pipeline, bad_raw
    )
    assert not bad_mismatches
    assert bad_facts == evidence.project_relation_result(bad_result)

    pair_raw = bad_pair_path.read_bytes()
    binding_raw = bad_binding_path.read_bytes()

    def endpoint_for_binding(binding_value: dict[str, object]) -> bytes:
        rebound_result = copy.deepcopy(bad_result)
        rebound_result["reductionBinding"]["canonicalBindingDigest"] = (
            canonical.canonical_digest(binding_value)
        )
        rebound_preimage = dict(rebound_result)
        rebound_preimage.pop("canonicalResultDigest")
        rebound_result["canonicalResultDigest"] = canonical.canonical_digest(
            rebound_preimage
        )
        return canonical.canonical_bytes(rebound_result)

    snapshot_rebound = copy.deepcopy(bad_binding)
    snapshot_row = next(
        row for row in snapshot_rebound["files"] if row["role"] == "snapshot"
    )
    snapshot_row["path"] = "policy.sps.yaml"
    snapshot_row["sha256"] = hashlib.sha256(
        (bad_case / "policy.sps.yaml").read_bytes()
    ).hexdigest()
    bad_binding_path.write_bytes(canonical.canonical_bytes(snapshot_rebound))
    rejected(
        bad_snapshot,
        bad_pipeline,
        endpoint_for_binding(snapshot_rebound),
        "snapshot role must name the fixed case-local snapshot.yaml",
    )
    bad_binding_path.write_bytes(binding_raw)

    pair_mutations = {
        "bad-state": (
            pair_raw.replace(
                b"bad_state: public-control-successor-mismatch",
                b"bad_state: wrong-bad-state",
                1,
            ),
            "must match snapshot bad_state",
        ),
        "first-bad-locator": (
            pair_raw.replace(
                b"kind: BranchSuccessor\n    field: successor",
                b"kind: Output\n    field: valueBytes\n    id: other-output",
                1,
            ),
            "must exactly match the snapshot's sole first_bad event",
        ),
    }
    for name, (mutated_pair, expected_error) in pair_mutations.items():
        assert mutated_pair != pair_raw, name
        bad_pair_path.write_bytes(mutated_pair)
        rebound_binding = copy.deepcopy(bad_binding)
        rebound_binding["counterexamplePair"]["sha256"] = hashlib.sha256(
            mutated_pair
        ).hexdigest()
        bad_binding_path.write_bytes(canonical.canonical_bytes(rebound_binding))
        rejected(
            bad_snapshot,
            bad_pipeline,
            endpoint_for_binding(rebound_binding),
            expected_error,
        )
    bad_pair_path.write_bytes(pair_raw)
    bad_binding_path.write_bytes(binding_raw)

    bad_pair_path.unlink()
    rejected(
        bad_snapshot,
        bad_pipeline,
        bad_raw,
        "cannot read counterexample pair",
    )
    bad_pair_path.write_bytes(pair_raw + b"\n")
    rejected(
        bad_snapshot,
        bad_pipeline,
        bad_raw,
        "counterexample pair raw-byte digest mismatch",
    )

    semantic_pair = pair_raw.replace(
        b'hex: "00000001"', b'hex: "00000000"', 1
    )
    assert semantic_pair != pair_raw
    bad_pair_path.write_bytes(semantic_pair)
    semantic_binding = copy.deepcopy(bad_binding)
    semantic_binding["counterexamplePair"]["sha256"] = hashlib.sha256(
        semantic_pair
    ).hexdigest()
    bad_binding_path.write_bytes(canonical.canonical_bytes(semantic_binding))
    rejected(
        bad_snapshot,
        bad_pipeline,
        endpoint_for_binding(semantic_binding),
        "at least one High component must differ",
    )

    print("relation-reference endpoint refusals passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
