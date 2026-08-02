"""Strict synthetic counterexample-pair binding for harness reductions."""

from __future__ import annotations

import re
from typing import Any, Mapping

from .engine import CompiledProgram
from .errors import SchemaError
from .model import Coalition, require_exact_keys, require_identifier
from .replay import ReplayRecord, replay_witness
from .strict_yaml import load_strict_block_yaml


PAIR_FORMAT = "SPS-Harness-Synthetic-Counterexample-Pair-v1"
PAIR_CLAIM_BOUNDARY = "NonClaimableFixtureOracle"
PAIR_SOURCE_CLASS = "SyntheticTestData"
_HEX = re.compile(r"[0-9a-f]+")


def load_counterexample_pair(raw: bytes, source: str) -> dict[str, Any]:
    return load_strict_block_yaml(raw, source)


def validate_and_replay_counterexample_pair(
    value: Any,
    fixture: Mapping[str, Any],
    binding: Mapping[str, Any],
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
) -> None:
    """Validate and independently replay one human-selected synthetic pair.

    No witness, values, replay record, or acceptance flag is returned to the
    evidence serializer. Successful return is only a fail-closed gate.
    """

    require_exact_keys(
        value,
        {
            "format_id",
            "claim_boundary",
            "source_class",
            "entry",
            "coalition",
            "inputs",
            "expected",
        },
        "counterexample pair",
    )
    if (
        value["format_id"] != PAIR_FORMAT
        or value["claim_boundary"] != PAIR_CLAIM_BOUNDARY
        or value["source_class"] != PAIR_SOURCE_CLASS
    ):
        raise SchemaError("counterexample pair has an unsafe authority boundary")
    require_identifier(value["entry"], "counterexample pair.entry")
    if value["entry"] != binding["entry"]:
        raise SchemaError("counterexample pair entry differs from reduction binding")
    principals = value["coalition"]
    if (
        not isinstance(principals, list)
        or principals != sorted(set(principals))
        or principals != binding["coalition"]["principals"]
    ):
        raise SchemaError("counterexample pair coalition differs from reduction binding")
    for index, principal in enumerate(principals):
        require_identifier(principal, f"counterexample pair.coalition[{index}]")

    inputs = value["inputs"]
    require_exact_keys(
        inputs,
        {"low_equal", "high_left", "high_right"},
        "counterexample pair.inputs",
    )
    for name in ("low_equal", "high_left", "high_right"):
        if not isinstance(inputs[name], dict):
            raise SchemaError(f"counterexample pair.inputs.{name}: expected mapping")

    scalar_rows = {row["component"]: row for row in binding["arguments"]}
    root_rows = {
        row["component"]: row
        for row in binding["roots"]
        if row["storageKind"] == "ABIArgument"
    }
    if set(scalar_rows) & set(root_rows):
        raise SchemaError("counterexample pair component and ABI-root IDs overlap")
    expected_low = {
        row["component"]
        for row in binding["arguments"]
        if row["classification"] == "Low"
    } | {
        row["component"]
        for row in binding["roots"]
        if row["storageKind"] == "ABIArgument"
        and row["initialClassification"] == "Low"
    }
    expected_high = {
        row["component"]
        for row in binding["arguments"]
        if row["classification"] == "High"
    } | {
        row["component"]
        for row in binding["roots"]
        if row["storageKind"] == "ABIArgument"
        and row["initialClassification"] == "High"
    }
    if set(inputs["low_equal"]) != expected_low:
        raise SchemaError("counterexample pair Low-equal input inventory differs")
    if set(inputs["high_left"]) != expected_high or set(inputs["high_right"]) != expected_high:
        raise SchemaError("counterexample pair High input inventory differs")

    witness: dict[str, int] = {}
    high_differs = False
    roots_by_id = {
        root["id"]: root for root in fixture["input"]["program"]["abi"]["roots"]
    }
    for component_id in sorted(expected_low):
        tagged = inputs["low_equal"][component_id]
        if component_id in scalar_rows:
            row = scalar_rows[component_id]
            materialized = _materialize_scalar(tagged, row, component_id)
            witness[f"L.input.{row['referenceInput']}"] = materialized
            witness[f"R.input.{row['referenceInput']}"] = materialized
        else:
            _materialize_root(
                tagged, root_rows[component_id], roots_by_id, component_id
            )
    for component_id in sorted(expected_high):
        left_tagged = inputs["high_left"][component_id]
        right_tagged = inputs["high_right"][component_id]
        if component_id in scalar_rows:
            row = scalar_rows[component_id]
            left_value = _materialize_scalar(left_tagged, row, component_id)
            right_value = _materialize_scalar(right_tagged, row, component_id)
            witness[f"L.input.{row['referenceInput']}"] = left_value
            witness[f"R.input.{row['referenceInput']}"] = right_value
            high_differs |= left_value != right_value
        else:
            left_bytes = _materialize_root(
                left_tagged, root_rows[component_id], roots_by_id, component_id
            )
            right_bytes = _materialize_root(
                right_tagged, root_rows[component_id], roots_by_id, component_id
            )
            high_differs |= left_bytes != right_bytes
    if not high_differs:
        raise SchemaError("counterexample pair does not vary any High component")

    expected = value["expected"]
    require_exact_keys(
        expected,
        {"bad_state", "first_difference"},
        "counterexample pair.expected",
    )
    require_identifier(expected["bad_state"], "counterexample pair.expected.bad_state")
    difference = expected["first_difference"]
    if not isinstance(difference, dict) or set(difference) not in (
        {"kind", "field"},
        {"kind", "field", "id"},
    ):
        raise SchemaError("counterexample pair first_difference has wrong fields")
    require_identifier(difference["kind"], "counterexample pair first_difference.kind")
    require_identifier(difference["field"], "counterexample pair first_difference.field")
    if "id" in difference:
        require_identifier(difference["id"], "counterexample pair first_difference.id")
    fixture_difference = fixture["expected"]["auditAll"]["firstDifference"]
    if fixture_difference is None or {
        "kind": difference["kind"],
        "field": difference["field"],
    } != fixture_difference:
        raise SchemaError("counterexample pair first difference differs from fixture")

    replay = replay_witness(left, right, coalition, witness)
    _validate_replay_difference(replay, difference)


def _materialize_scalar(tagged: Any, row: Mapping[str, Any], component_id: str) -> int:
    require_exact_keys(tagged, {"bitvector"}, f"counterexample pair input {component_id}")
    payload = tagged["bitvector"]
    require_exact_keys(
        payload, {"width", "hex"}, f"counterexample pair input {component_id}.bitvector"
    )
    width = payload["width"]
    raw_hex = payload["hex"]
    if width != row["fullWidth"]:
        raise SchemaError(f"counterexample pair input {component_id} has wrong full width")
    if not isinstance(raw_hex, str) or not _HEX.fullmatch(raw_hex):
        raise SchemaError(f"counterexample pair input {component_id} has invalid lowercase hex")
    if len(raw_hex) != (width + 3) // 4:
        raise SchemaError(f"counterexample pair input {component_id} hex is not fixed-width")
    value = int(raw_hex, 16)
    if value >= 1 << width:
        raise SchemaError(f"counterexample pair input {component_id} has nonzero padding bits")
    if value >= 1 << row["reducedWidth"]:
        raise SchemaError(
            f"counterexample pair input {component_id} cannot be losslessly materialized"
        )
    return value


def _materialize_root(
    tagged: Any,
    row: Mapping[str, Any],
    roots_by_id: Mapping[str, Mapping[str, Any]],
    component_id: str,
) -> tuple[int, ...]:
    require_exact_keys(tagged, {"bytes"}, f"counterexample pair input {component_id}")
    payload = tagged["bytes"]
    require_exact_keys(
        payload, {"length", "hex"}, f"counterexample pair input {component_id}.bytes"
    )
    length = payload["length"]
    raw_hex = payload["hex"]
    if length != row["byteLength"]:
        raise SchemaError(f"counterexample pair root {component_id} has wrong byte length")
    if (
        not isinstance(raw_hex, str)
        or not _HEX.fullmatch(raw_hex)
        or len(raw_hex) != 2 * length
    ):
        raise SchemaError(f"counterexample pair root {component_id} has invalid fixed-width hex")
    materialized = tuple(bytes.fromhex(raw_hex))
    root = roots_by_id[row["referenceRoot"]]
    if materialized != tuple(root["initialBytes"]):
        raise SchemaError(
            f"counterexample pair root {component_id} cannot be losslessly materialized"
        )
    return materialized


def _validate_replay_difference(
    replay: ReplayRecord, expected: Mapping[str, str]
) -> None:
    if not replay.accepted or replay.first_bad_event_ordinal is None:
        raise SchemaError("counterexample pair did not replay to a bad state")
    ordinal = replay.first_bad_event_ordinal
    if ordinal >= len(replay.left_trace):
        actual_kind = "Output"
        actual_field = "valueBytes"
        event_id = None
    else:
        event = replay.left_trace[ordinal]
        actual_kind = event.kind
        actual_field = "successor" if event.kind == "BranchSuccessor" else "valueBytes"
        event_id = event.site if event.kind == "BranchSuccessor" else event.output_id
    if (actual_kind, actual_field) != (expected["kind"], expected["field"]):
        raise SchemaError("counterexample pair replay reached a different first difference")
    if "id" in expected and expected["id"] != event_id:
        raise SchemaError("counterexample pair replay reached a different event ID")
