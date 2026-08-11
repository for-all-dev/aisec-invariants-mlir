#!/usr/bin/env python3
"""Focused fail-closed mutations for the relation reduction binding bridge."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Callable

import yaml


def _json(path: Path) -> dict:
    value = json.loads(path.read_text())
    assert isinstance(value, dict)
    return value


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def _update_role_digest(binding_path: Path, role: str, target: Path) -> None:
    binding = _json(binding_path)
    row = next(item for item in binding["files"] if item["role"] == role)
    row["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    _write_json(binding_path, binding)


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    sys.path[:0] = [str(root / "tools"), str(root / "integration" / "Inputs")]
    import checkpoint_extractors
    import checkpoint_model
    import run_relation_reference_fixtures as dispatcher

    canonical, evidence = dispatcher._reference_api(root)

    def validate(case_name: str) -> None:
        snapshot = checkpoint_model.load_snapshot(
            root / "fixtures" / "precision-control" / case_name / "snapshot.yaml",
            root,
        )
        dispatcher._validate_case(
            root,
            snapshot,
            snapshot.pipelines["relation-reference"],
            checkpoint_model,
            checkpoint_extractors,
            canonical,
            evidence,
        )

    for case in (
        "different-successor-bad",
        "identical-successor",
        "missing-overwrite-bad",
        "offset-disjoint",
        "offset-overlap-bad",
        "overwritten-slot",
        "xor-cancellation",
        "xor-secret-output-bad",
    ):
        validate(case)

    def rejected(
        case: str,
        paths: list[Path],
        mutation: Callable[[], None],
        expected: str,
    ) -> None:
        original = {path: path.read_bytes() for path in paths}
        try:
            mutation()
            try:
                validate(case)
            except dispatcher.BindingError as error:
                assert expected in str(error), (expected, str(error))
            else:
                raise AssertionError(f"mutation unexpectedly accepted: {expected}")
        finally:
            for path, raw in original.items():
                path.write_bytes(raw)

    identical = root / "fixtures" / "precision-control" / "identical-successor"
    identical_binding = identical / "relation-reference" / "binding.json"

    def wrong_argument_index() -> None:
        value = _json(identical_binding)
        value["arguments"][0]["argumentIndex"] = 7
        _write_json(identical_binding, value)

    rejected(
        "identical-successor",
        [identical_binding],
        wrong_argument_index,
        "binding/ABI argument index",
    )

    def wrong_argument_name() -> None:
        value = _json(identical_binding)
        value["arguments"][0]["argumentName"] = "wrong_name"
        _write_json(identical_binding, value)

    rejected(
        "identical-successor",
        [identical_binding],
        wrong_argument_name,
        "binding/MLIR argument name",
    )

    def stale_hash() -> None:
        value = _json(identical_binding)
        value["files"][0]["sha256"] = "0" * 64
        _write_json(identical_binding, value)

    rejected(
        "identical-successor",
        [identical_binding],
        stale_hash,
        "binding file digest mismatch",
    )

    abi_path = identical / "abi.sps.yaml"

    def signature_drift() -> None:
        abi = yaml.safe_load(abi_path.read_text())
        abi["entry"]["function-type"] = "i32 (i32)"
        abi_path.write_text(yaml.safe_dump(abi, sort_keys=False))
        _update_role_digest(identical_binding, "abi", abi_path)

    rejected(
        "identical-successor",
        [abi_path, identical_binding],
        signature_drift,
        "MLIR/ABI signature",
    )

    def coalition_drift() -> None:
        value = _json(identical_binding)
        value["coalition"]["policyAdversaryIndex"] = 1
        _write_json(identical_binding, value)

    rejected(
        "identical-successor",
        [identical_binding],
        coalition_drift,
        "requires policy adversary maximal[0]",
    )

    def observation_drift() -> None:
        value = _json(identical_binding)
        value["observations"] = value["observations"][1:]
        _write_json(identical_binding, value)

    rejected(
        "identical-successor",
        [identical_binding],
        observation_drift,
        "binding/snapshot observations",
    )

    identical_fixture = identical / "relation-reference" / "fixture.json"

    def successor_token_drift() -> None:
        fixture = _json(identical_fixture)
        fixture["input"]["program"]["statements"][0]["elseSuccessor"] = "secret.false"
        _write_json(identical_fixture, fixture)
        _update_role_digest(identical_binding, "referenceFixture", identical_fixture)

    rejected(
        "identical-successor",
        [identical_fixture, identical_binding],
        successor_token_drift,
        "MLIR/reduction successor identity",
    )

    xor = root / "fixtures" / "precision-control" / "xor-cancellation"
    xor_fixture = xor / "relation-reference" / "fixture.json"
    xor_binding = xor / "relation-reference" / "binding.json"

    def xor_operand_drift() -> None:
        fixture = _json(xor_fixture)
        fixture["input"]["program"]["statements"][0]["value"]["xor"][1] = {
            "const": {"width": 2, "value": 0}
        }
        _write_json(xor_fixture, fixture)
        _update_role_digest(xor_binding, "referenceFixture", xor_fixture)

    rejected(
        "xor-cancellation",
        [xor_fixture, xor_binding],
        xor_operand_drift,
        "MLIR/reduction XOR operands",
    )

    overwritten = root / "fixtures" / "precision-control" / "overwritten-slot"
    overwritten_fixture = overwritten / "relation-reference" / "fixture.json"
    overwritten_binding = overwritten / "relation-reference" / "binding.json"

    def removed_overwrite() -> None:
        fixture = _json(overwritten_fixture)
        del fixture["input"]["program"]["statements"][1]
        _write_json(overwritten_fixture, fixture)
        _update_role_digest(
            overwritten_binding, "referenceFixture", overwritten_fixture
        )

    rejected(
        "overwritten-slot",
        [overwritten_fixture, overwritten_binding],
        removed_overwrite,
        "MLIR/reduction stores",
    )

    offset = root / "fixtures" / "precision-control" / "offset-disjoint"
    offset_fixture = offset / "relation-reference" / "fixture.json"
    offset_binding = offset / "relation-reference" / "binding.json"

    def load_offset_drift() -> None:
        fixture = _json(offset_fixture)
        load = fixture["input"]["program"]["statements"][2]["value"]["extract"][
            "value"
        ]["load"]
        load["offset"] = 4
        _write_json(offset_fixture, fixture)
        _update_role_digest(offset_binding, "referenceFixture", offset_fixture)

    rejected(
        "offset-disjoint",
        [offset_fixture, offset_binding],
        load_offset_drift,
        "MLIR/reduction loads",
    )

    offset_abi = offset / "abi.sps.yaml"

    def terminal_order_drift() -> None:
        abi = yaml.safe_load(offset_abi.read_text())
        abi["terminal-output-order"]["normal-value"] = ["return", "buffer"]
        offset_abi.write_text(yaml.safe_dump(abi, sort_keys=False))
        _update_role_digest(offset_binding, "abi", offset_abi)

    rejected(
        "offset-disjoint",
        [offset_abi, offset_binding],
        terminal_order_drift,
        "reference/ABI terminal output order",
    )

    print("relation-reference cross-layer binding mutations passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
