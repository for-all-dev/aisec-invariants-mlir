#!/usr/bin/env python3
"""Check the four unversioned fixture-verifier wire schemas."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

import jsonschema


SCHEMAS = {
    "snapshot": "SPS-Harness-Fixture-Snapshot.schema.json",
    "fragment": "SPS-Harness-Trace-Fragment.schema.json",
    "trace": "SPS-Harness-Verification-Trace.schema.json",
    "result": "SPS-Harness-Verification-Result.schema.json",
}

FORMATS = {
    "snapshot": "SPS-Harness-Fixture-Snapshot",
    "fragment": "SPS-Harness-Trace-Fragment",
    "trace": "SPS-Harness-Verification-Trace",
    "result": "SPS-Harness-Verification-Result",
}


def load_schemas(root: Path) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for key, name in SCHEMAS.items():
        path = root / name
        value = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(value, dict), path
        loaded[key] = value
    return loaded


def check_structure(schemas: dict[str, dict[str, Any]]) -> None:
    for key, schema in schemas.items():
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["properties"]["format"]["const"] == FORMATS[key]
        assert re.search(r"-v[0-9]+(?:$|[^A-Za-z0-9])", FORMATS[key]) is None

    shared = ("caseId", "mlirSymbol", "stableId", "pipelineId", "eventKind", "eventField")
    snapshot_defs = schemas["snapshot"]["$defs"]
    for name in shared:
        expected = snapshot_defs[name]
        for key in ("fragment", "trace", "result"):
            assert schemas[key]["$defs"][name] == expected, (key, name)

    expected_event_selector = snapshot_defs["eventSelector"]
    assert len(expected_event_selector["oneOf"]) == 15
    for key in ("fragment", "trace", "result"):
        assert schemas[key]["$defs"]["eventSelector"] == expected_event_selector

    assert (
        schemas["fragment"]["$defs"]["factValue"]
        == schemas["trace"]["$defs"]["factValue"]
    )
    assert (
        schemas["fragment"]["$defs"]["expectationBlindKey"]
        == schemas["trace"]["$defs"]["expectationBlindKey"]
    )
    assert (
        schemas["snapshot"]["$defs"]["safeFactObjectKey"]
        == schemas["result"]["$defs"]["safeFactObjectKey"]
    )

    pointer_pattern = schemas["result"]["$defs"]["jsonPointer"]["pattern"]
    pointer = re.compile(pointer_pattern)
    assert pointer.fullmatch("")
    assert pointer.fullmatch("/expect/position/tag")
    assert pointer.fullmatch("/expect/pipelines/modeled-shape/properties/operation.names")
    assert not pointer.fullmatch("expect/position")
    assert not pointer.fullmatch("/bad~escape")


def golden_instances() -> dict[str, dict[str, Any]]:
    digest = "0" * 64
    selector = {"kind": "BranchSuccessor", "field": "successor"}
    capture = {
        "state": "Captured",
        "kind": "mlir",
        "extractor": "mlir-structure",
        "endpoint_sha256": digest,
        "facts": {"operation.names": ["llvm.icmp", "llvm.cond_br"]},
    }
    counterexample = {
        "tag": "Validated",
        "cause": "world-control-location-mismatch",
        "first_difference": selector,
        "pair_sha256": digest,
        "replay_sha256": digest,
        "validator": {"id": "relation-reference-runner", "build_sha256": digest},
    }
    snapshot = {
        "format": FORMATS["snapshot"],
        "case": "loop-bounds/secret-trip-count-bad",
        "entry": "bound_secret_trip_count_bad",
        "expect": {
            "position": {
                "tag": "Counterexample",
                "cause": "world-control-location-mismatch",
                "first_difference": selector,
            },
            "deployment": "Open",
            "policy": "Complete",
            "events": [selector],
            "pipelines": {
                "modeled-shape": {
                    "kind": "mlir",
                    "properties": {
                        "operation.names": {
                            "ordered": ["llvm.icmp", "llvm.cond_br"]
                        }
                    },
                }
            },
        },
        "because": "the first successors differ",
    }
    fragment = {
        "format": FORMATS["fragment"],
        "session": "run-1",
        "case": snapshot["case"],
        "entry": snapshot["entry"],
        "record": {
            "tag": "PipelineCapture",
            "pipeline": "modeled-shape",
            "capture": capture,
        },
    }
    trace = {
        "format": FORMATS["trace"],
        "case": snapshot["case"],
        "entry": snapshot["entry"],
        "authority": "TestOnly",
        "sensitivity": "SyntheticTestData",
        "captures": {"modeled-shape": capture},
        "decision": {
            "event_coverage": [selector],
            "counterexample": counterexample,
            "blockers": [],
            "all_required_gates_closed": False,
            "deployment": "Open",
            "policy": "Complete",
        },
    }
    result = {
        "format": FORMATS["result"],
        "authority": "TestOnly",
        "sensitivity": "SyntheticTestData",
        "claimable": False,
        "sps_model_status": "NotComputed",
        "outcome": {
            "tag": "Matched",
            "case": snapshot["case"],
            "entry": snapshot["entry"],
            "actual": {
                "position": snapshot["expect"]["position"],
                "deployment": "Open",
                "policy": "Complete",
            },
        },
        "pipelines": [{"pipeline": "modeled-shape", "comparison": "Matched"}],
        "consumed": [
            {
                "expectation_path": "/expect/pipelines/modeled-shape/properties/operation.names/ordered",
                "actual_path": "/captures/modeled-shape/facts/operation.names",
                "check": "Ordered",
                "disposition": "Matched",
                "expected": ["llvm.icmp", "llvm.cond_br"],
                "actual": {
                    "state": "Present",
                    "value": ["llvm.icmp", "llvm.cond_br"],
                },
            }
        ],
        "ignored": [{"path": "/because", "reason": "ExplanationOnly"}],
        "issues": [],
    }
    return {"snapshot": snapshot, "fragment": fragment, "trace": trace, "result": result}


def check_with_jsonschema(
    schemas: dict[str, dict[str, Any]], instances: dict[str, dict[str, Any]]
) -> None:
    validators = {}
    for key, schema in schemas.items():
        jsonschema.Draft202012Validator.check_schema(schema)
        validators[key] = jsonschema.Draft202012Validator(schema)
        validators[key].validate(instances[key])

    wrong_event = copy.deepcopy(instances["trace"])
    wrong_event["decision"]["event_coverage"][0]["field"] = "valueBytes"
    assert not validators["trace"].is_valid(wrong_event)

    newline_snapshot = copy.deepcopy(instances["snapshot"])
    newline_snapshot["case"] += "\n"
    assert not validators["snapshot"].is_valid(newline_snapshot)

    newline_fragment = copy.deepcopy(instances["fragment"])
    newline_fragment["session"] += "\n"
    assert not validators["fragment"].is_valid(newline_fragment)

    newline_trace = copy.deepcopy(instances["trace"])
    newline_trace["entry"] += "\n"
    assert not validators["trace"].is_valid(newline_trace)

    newline_result = copy.deepcopy(instances["result"])
    newline_result["pipelines"][0]["pipeline"] += "\n"
    assert not validators["result"].is_valid(newline_result)

    newline_event_id = copy.deepcopy(instances["snapshot"])
    newline_event_id["expect"]["events"][0]["id"] = "event\n"
    assert not validators["snapshot"].is_valid(newline_event_id)

    newline_digest = copy.deepcopy(instances["fragment"])
    newline_digest["record"]["capture"]["endpoint_sha256"] += "\n"
    assert not validators["fragment"].is_valid(newline_digest)

    newline_fact_key = copy.deepcopy(instances["trace"])
    newline_fact_key["captures"]["modeled-shape"]["facts"][
        "operation.names\n"
    ] = newline_fact_key["captures"]["modeled-shape"]["facts"].pop(
        "operation.names"
    )
    assert not validators["trace"].is_valid(newline_fact_key)

    for wire in ("fragment", "trace"):
        poisoned = copy.deepcopy(instances[wire])
        if wire == "fragment":
            facts = poisoned["record"]["capture"]["facts"]
        else:
            facts = poisoned["captures"]["modeled-shape"]["facts"]
        facts["nested"] = {"e_x-p.e c t e d-result": "copied"}
        assert not validators[wire].is_valid(poisoned)

        match_poisoned = copy.deepcopy(instances[wire])
        if wire == "fragment":
            facts = match_poisoned["record"]["capture"]["facts"]
        else:
            facts = match_poisoned["captures"]["modeled-shape"]["facts"]
        facts["nested"] = {"matching-details": "precompared"}
        assert not validators[wire].is_valid(match_poisoned)

    for wire in ("snapshot", "fragment", "trace"):
        boundary = copy.deepcopy(instances[wire])
        oversized = copy.deepcopy(instances[wire])
        if wire == "snapshot":
            boundary_properties = boundary["expect"]["pipelines"][
                "modeled-shape"
            ]["properties"]
            oversized_properties = oversized["expect"]["pipelines"][
                "modeled-shape"
            ]["properties"]
        elif wire == "fragment":
            boundary_properties = boundary["record"]["capture"]["facts"]
            oversized_properties = oversized["record"]["capture"]["facts"]
        else:
            boundary_properties = boundary["captures"]["modeled-shape"]["facts"]
            oversized_properties = oversized["captures"]["modeled-shape"]["facts"]
        boundary_properties["k" * 256] = (
            {"equals": "value"} if wire == "snapshot" else "value"
        )
        oversized_properties["k" * 257] = (
            {"equals": "value"} if wire == "snapshot" else "value"
        )
        validators[wire].validate(boundary)
        assert not validators[wire].is_valid(oversized)

    unknown_field = copy.deepcopy(instances["snapshot"])
    unknown_field["unexpected"] = True
    assert not validators["snapshot"].is_valid(unknown_field)

    nul_because = copy.deepcopy(instances["snapshot"])
    nul_because["because"] = "invalid\0explanation"
    assert not validators["snapshot"].is_valid(nul_because)

    for wire in ("snapshot", "fragment", "trace", "result"):
        nul_fact = copy.deepcopy(instances[wire])
        if wire == "snapshot":
            matcher = nul_fact["expect"]["pipelines"]["modeled-shape"][
                "properties"
            ]["operation.names"]
            matcher.clear()
            matcher["equals"] = "invalid\0fact"
        elif wire == "fragment":
            nul_fact["record"]["capture"]["facts"]["nul.value"] = "a\0b"
        elif wire == "trace":
            nul_fact["captures"]["modeled-shape"]["facts"]["nul.value"] = (
                "a\0b"
            )
        else:
            nul_fact["consumed"][0]["actual"] = {
                "state": "Present",
                "value": "a\0b",
            }
        assert not validators[wire].is_valid(nul_fact)

    nul_nested_key = copy.deepcopy(instances["fragment"])
    nul_nested_key["record"]["capture"]["facts"]["nested"] = {
        "bad\0key": "value"
    }
    assert not validators["fragment"].is_valid(nul_nested_key)

    surrogate_because = copy.deepcopy(instances["snapshot"])
    surrogate_because["because"] = "invalid\ud800explanation"
    assert not validators["snapshot"].is_valid(surrogate_because)

    for wire in ("snapshot", "fragment", "trace", "result"):
        surrogate_fact = copy.deepcopy(instances[wire])
        if wire == "snapshot":
            matcher = surrogate_fact["expect"]["pipelines"]["modeled-shape"][
                "properties"
            ]["operation.names"]
            matcher.clear()
            matcher["equals"] = "invalid\ud800fact"
        elif wire == "fragment":
            surrogate_fact["record"]["capture"]["facts"]["bad.value"] = (
                "a\ud800b"
            )
        elif wire == "trace":
            surrogate_fact["captures"]["modeled-shape"]["facts"]["bad.value"] = (
                "a\ud800b"
            )
        else:
            surrogate_fact["consumed"][0]["actual"] = {
                "state": "Present",
                "value": "a\ud800b",
            }
        assert not validators[wire].is_valid(surrogate_fact)

    surrogate_nested_key = copy.deepcopy(instances["trace"])
    surrogate_nested_key["captures"]["modeled-shape"]["facts"]["nested"] = {
        "bad\ud800key": "value"
    }
    assert not validators["trace"].is_valid(surrogate_nested_key)

    for invalid_key in ("bad\0key", "bad\ud800key"):
        nested_snapshot = copy.deepcopy(instances["snapshot"])
        matcher = nested_snapshot["expect"]["pipelines"]["modeled-shape"][
            "properties"
        ]["operation.names"]
        matcher.clear()
        matcher["equals"] = {invalid_key: "value"}
        assert not validators["snapshot"].is_valid(nested_snapshot)

        nested_result = copy.deepcopy(instances["result"])
        nested_result["consumed"][0]["actual"] = {
            "state": "Present",
            "value": {invalid_key: "value"},
        }
        assert not validators["result"].is_valid(nested_result)

    nul_failed_text = copy.deepcopy(instances["fragment"])
    nul_failed_text["record"]["capture"] = {
        "state": "ProducerFailed",
        "kind": "mlir",
        "extractor": "build",
        "error": "failed\0detail",
        "blocked_by": ["compile\0step"],
    }
    assert not validators["fragment"].is_valid(nul_failed_text)

    oversized_integer = copy.deepcopy(instances["snapshot"])
    oversized_integer["expect"]["pipelines"]["modeled-shape"]["properties"][
        "operation.names"
    ] = {"equals": 1 << 63}
    assert not validators["snapshot"].is_valid(oversized_integer)

    null_actual = copy.deepcopy(instances["result"])
    null_actual["consumed"][0]["actual"] = None
    assert not validators["result"].is_valid(null_actual)

    missing_actual = copy.deepcopy(instances["result"])
    missing_actual["outcome"]["tag"] = "Mismatched"
    missing_actual["consumed"][0]["disposition"] = "Mismatched"
    missing_actual["consumed"][0]["actual"] = {"state": "Missing"}
    missing_actual["issues"] = [
        {
            "kind": "ExpectationMismatch",
            "phase": "Compare",
            "code": "ExpectationMismatch",
            "path": missing_actual["consumed"][0]["expectation_path"],
            "message": "expected fact is missing",
        }
    ]
    validators["result"].validate(missing_actual)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} SCHEMA_DIRECTORY")
    schemas = load_schemas(Path(sys.argv[1]))
    check_structure(schemas)
    check_with_jsonschema(schemas, golden_instances())
    print("fixture wire schemas passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
