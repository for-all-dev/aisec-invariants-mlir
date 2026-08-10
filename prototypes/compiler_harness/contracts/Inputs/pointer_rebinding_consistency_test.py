#!/usr/bin/env python3
"""Fail-closed mutations for the pointer-rebinding consistency validator."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Callable

import yaml


def _yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict)
    return value


def _write_yaml(path: Path, value: dict) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False))


def _json(path: Path) -> dict:
    value = json.loads(path.read_text())
    assert isinstance(value, dict)
    return value


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(root / "tools"))
    import check_pointer_rebinding as pointer_rebinding

    fixtures = root / "fixtures" / "pointer-rebinding"
    bad = fixtures / "disjoint-select-bad"
    control = fixtures / "same-allocation-control"
    spill = fixtures / "pointer-spill-unsupported"

    pointer_rebinding.validate(root)

    def rejected(
        paths: list[Path], mutation: Callable[[], None], expected: str
    ) -> None:
        originals = {path: path.read_bytes() for path in paths}
        try:
            mutation()
            try:
                pointer_rebinding.validate(root)
            except pointer_rebinding.PointerRebindingError as error:
                assert expected in str(error), (expected, str(error))
            else:
                raise AssertionError(f"mutation unexpectedly accepted: {expected}")
        finally:
            for path, raw in originals.items():
                path.write_bytes(raw)

    bad_abi = bad / "abi.sps.yaml"

    def bad_becomes_same_allocation() -> None:
        value = _yaml(bad_abi)
        row = next(
            row
            for row in value["aliases"]["relations"]
            if set(row["roots"]) == {"left", "right"}
        )
        row["relation"] = "same-allocation"
        _write_yaml(bad_abi, value)

    rejected([bad_abi], bad_becomes_same_allocation, "selected-root relation")

    control_abi = control / "abi.sps.yaml"

    def control_becomes_disjoint() -> None:
        value = _yaml(control_abi)
        row = next(
            row
            for row in value["aliases"]["relations"]
            if set(row["roots"]) == {"left", "right"}
        )
        row["relation"] = "disjoint"
        _write_yaml(control_abi, value)

    rejected([control_abi], control_becomes_disjoint, "selected-root relation")

    def omit_partition_pair() -> None:
        value = _yaml(bad_abi)
        value["aliases"]["relations"].pop()
        _write_yaml(bad_abi, value)

    rejected([bad_abi], omit_partition_pair, "cover every root pair exactly once")

    def duplicate_partition_pair() -> None:
        value = _yaml(bad_abi)
        value["aliases"]["relations"].append(
            copy.deepcopy(value["aliases"]["relations"][0])
        )
        _write_yaml(bad_abi, value)

    rejected([bad_abi], duplicate_partition_pair, "duplicate relation for root pair")

    def inconsistent_same_class_metadata() -> None:
        value = _yaml(control_abi)
        value["roots"]["right"]["address-space"] = 1
        _write_yaml(control_abi, value)

    rejected(
        [control_abi],
        inconsistent_same_class_metadata,
        "same-allocation roots",
    )

    bad_policy = bad / "policy.sps.yaml"

    def selector_is_public() -> None:
        value = _yaml(bad_policy)
        value["components"]["secret-selector"]["visibility"] = "public"
        _write_yaml(bad_policy, value)

    rejected([bad_policy], selector_is_public, "must remain High for observer")

    def hide_allocation_host() -> None:
        value = _yaml(bad_policy)
        value["hosts"]["compute"]["visibility"]["members"] = []
        _write_yaml(bad_policy, value)

    rejected([bad_policy], hide_allocation_host, "must be visible to observer")

    pair_path = bad / "counterexample-pair.yaml"

    def unequal_isolation_bytes() -> None:
        value = _yaml(pair_path)
        value["inputs"]["low_equal"]["right-input"]["bytes"]["hex"] = "2b"
        _write_yaml(pair_path, value)

    rejected([pair_path], unequal_isolation_bytes, "equal-byte isolation")

    bad_snapshot = bad / "snapshot.yaml"

    def wrong_first_event() -> None:
        value = _yaml(bad_snapshot)
        value["expect"]["final"]["events"][0]["field"] = "offsetClass"
        _write_yaml(bad_snapshot, value)

    rejected([bad_snapshot], wrong_first_event, "expect.final.events")

    def wrong_snapshot_status() -> None:
        value = _yaml(bad_snapshot)
        value["expect"]["final"]["model"]["status"] = "Proved"
        _write_yaml(bad_snapshot, value)

    rejected([bad_snapshot], wrong_snapshot_status, "expect.final.model.status")

    bad_artifact = bad / "candidate" / "artifact.ll"

    def introduce_earlier_branch() -> None:
        text = bad_artifact.read_text()
        marker = ") {\n"
        assert marker in text
        bad_artifact.write_text(
            text.replace(marker, marker + "  br i1 true, label %a, label %b\n", 1)
        )

    rejected([bad_artifact], introduce_earlier_branch, "conditional branch")

    spill_artifact = spill / "candidate" / "artifact.ll"

    def remove_pointer_store() -> None:
        text = spill_artifact.read_text()
        assert "store ptr" in text
        spill_artifact.write_text(text.replace("store ptr", "store i64", 1))

    rejected([spill_artifact], remove_pointer_store, "pointer-valued store")

    def remove_pointer_load() -> None:
        text = spill_artifact.read_text()
        assert "load ptr" in text
        spill_artifact.write_text(text.replace("load ptr", "load i64", 1))

    rejected([spill_artifact], remove_pointer_load, "pointer-valued load")

    bad_spec = bad / "candidate" / "bundle-spec.json"

    def candidate_topology_drift() -> None:
        value = _json(bad_spec)
        row = next(
            row
            for row in value["abi"]["alias_topology"]["relations"]
            if {row["left"], row["right"]} == {"left", "right"}
        )
        row["relation"] = "SameAllocation"
        _write_json(bad_spec, value)

    rejected([bad_spec], candidate_topology_drift, "cross-layer binding")

    spill_spec = spill / "candidate" / "bundle-spec.json"

    def wrong_spill_reason() -> None:
        value = _json(spill_spec)
        value["expected_report"]["expected"]["audit_all_expectations"][0][
            "query_outcome"
        ]["reason"]["reasonClassId"] = "UnsupportedInstruction"
        _write_json(spill_spec, value)

    rejected([spill_spec], wrong_spill_reason, "audit_all_expectations")

    pointer_rebinding.validate(root)
    print("pointer-rebinding consistency mutations passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
