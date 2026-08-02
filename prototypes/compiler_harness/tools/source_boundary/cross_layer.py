"""Validate logical references across one source-authored fixture stack."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import checkpoint_model


class CrossLayerError(ValueError):
    pass


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CrossLayerError(f"{where}: expected an object")
    return value


def _string_list(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        raise CrossLayerError(f"{where}: expected an array of strings")
    if value != sorted(set(value)):
        raise CrossLayerError(f"{where}: must be sorted and duplicate-free")
    return value


def _load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        value = checkpoint_model.strict_yaml_load(path.read_bytes(), source=str(path))
    except (OSError, checkpoint_model.CheckpointError) as error:
        raise CrossLayerError(str(error)) from error
    return _mapping(value, str(path))


def _load_json(path: Path) -> Mapping[str, Any]:
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise CrossLayerError(f"{path}: duplicate JSON field {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, json.JSONDecodeError) as error:
        raise CrossLayerError(f"cannot read {path}: {error}") from error
    return _mapping(value, str(path))


def _expect_equal(actual: object, expected: object, where: str) -> None:
    if actual != expected:
        raise CrossLayerError(f"{where}: expected {expected!r}, got {actual!r}")


def _visibility_ids(value: Any, where: str) -> set[str]:
    basis = _mapping(value, where)
    identifiers = set(
        _string_list(basis.get("world_visible"), f"{where}.world_visible")
    )
    members = _mapping(basis.get("member_visible"), f"{where}.member_visible")
    for principal, visible in members.items():
        identifiers.update(
            _string_list(visible, f"{where}.member_visible[{principal!r}]")
        )
    joint = basis.get("minimally_joint_visible")
    if not isinstance(joint, list):
        raise CrossLayerError(f"{where}.minimally_joint_visible: expected an array")
    for index, row in enumerate(joint):
        item = _mapping(row, f"{where}.minimally_joint_visible[{index}]")
        identifiers.update(
            _string_list(
                item.get("visible"),
                f"{where}.minimally_joint_visible[{index}].visible",
            )
        )
    return identifiers


def validate(
    *,
    source: Path,
    policy_path: Path,
    abi_path: Path,
    mlir_path: Path,
    candidate_policy_path: Path,
    candidate_release_path: Path,
    resolved: Mapping[str, Any],
) -> None:
    case = source.resolve().parent
    if mlir_path.resolve().parent != case:
        raise CrossLayerError("MLIR must be a sibling of the annotated source")
    policy = _load_yaml(policy_path)
    abi = _load_yaml(abi_path)
    candidate_policy = _load_json(candidate_policy_path)
    candidate_release = _load_json(candidate_release_path)
    try:
        mlir = mlir_path.read_text(encoding="utf-8")
    except OSError as error:
        raise CrossLayerError(f"cannot read {mlir_path}: {error}") from error

    entry = _mapping(abi.get("entry"), "ABI entry")
    _expect_equal(policy.get("entry"), entry.get("id"), "policy/ABI entry ID mismatch")
    source_symbol = entry.get("symbol")
    if not isinstance(source_symbol, str):
        raise CrossLayerError("ABI entry symbol must be a string")

    roles = candidate_policy.get("argument_roles")
    placement = candidate_policy.get("placement")
    if not isinstance(roles, list) or any(
        not isinstance(item, Mapping) for item in roles
    ):
        raise CrossLayerError("candidate policy argument_roles must be objects")
    if not isinstance(placement, list) or any(
        not isinstance(item, Mapping) for item in placement
    ):
        raise CrossLayerError("candidate policy placement must be objects")
    authored_model_symbols = [
        item.get("entry")
        for item in [*roles, *placement]
        if item.get("entry") is not None
    ]
    if any(not isinstance(symbol, str) for symbol in authored_model_symbols):
        raise CrossLayerError(
            "candidate policy must identify exactly one reduced-model entry symbol"
        )
    model_symbols = set(authored_model_symbols)
    if len(model_symbols) != 1:
        raise CrossLayerError(
            "candidate policy must identify exactly one reduced-model entry symbol"
        )
    model_symbol = next(iter(model_symbols))
    if not re.search(
        rf"(?m)^\s*llvm\.func\s+@{re.escape(model_symbol)}\s*\(", mlir
    ):
        raise CrossLayerError(f"MLIR has no reduced-model entry function {model_symbol!r}")

    component_ids = set(_mapping(policy.get("components"), "policy components"))
    carrier_ids = set(_mapping(abi.get("carriers"), "ABI carriers"))

    output_ids = set(_mapping(policy.get("outputs"), "policy outputs"))
    roots = _mapping(abi.get("roots"), "ABI roots")
    root_ids = set(roots)
    root_inputs = {
        _mapping(value, f"ABI root {identifier!r}").get("input")
        for identifier, value in roots.items()
        if _mapping(value, f"ABI root {identifier!r}").get("input") is not None
    }
    _expect_equal(
        carrier_ids | root_inputs,
        component_ids,
        "policy component/ABI input IDs mismatch",
    )
    root_outputs = {
        _mapping(value, f"ABI root {identifier!r}").get("output")
        for identifier, value in roots.items()
        if _mapping(value, f"ABI root {identifier!r}").get("output") is not None
    }
    return_value = entry.get("return")
    if isinstance(return_value, Mapping):
        root_outputs.add(return_value.get("output"))
    _expect_equal(root_outputs, output_ids, "policy output/ABI output IDs mismatch")

    def refs(name: str) -> set[str]:
        return set(
            re.findall(
                rf'\bsps\.{re.escape(name)}\s*=\s*"([A-Za-z][A-Za-z0-9._-]*)"',
                mlir,
            )
        )

    _expect_equal(refs("component_ref"), component_ids, "MLIR component references mismatch")
    _expect_equal(refs("abi_root_ref"), root_ids, "MLIR root references mismatch")
    _expect_equal(refs("output_ref"), output_ids, "MLIR output references mismatch")

    releases = _mapping(policy.get("releases"), "policy releases")
    release_ids = set(releases)
    _expect_equal(refs("release_ref"), release_ids, "MLIR release references mismatch")
    _expect_equal(
        set(
            _string_list(
                candidate_policy.get("release_bindings"),
                "candidate policy release_bindings",
            )
        ),
        release_ids,
        "candidate policy release_bindings mismatch",
    )
    _expect_equal(
        set(
            _string_list(
                candidate_policy.get("components"), "candidate policy components"
            )
        ),
        component_ids,
        "candidate policy component IDs mismatch",
    )
    _expect_equal(
        _visibility_ids(candidate_policy.get("output_visibility"), "candidate output_visibility"),
        output_ids,
        "candidate policy output IDs mismatch",
    )

    candidate_entries = candidate_release.get("entries")
    if not isinstance(candidate_entries, list) or any(
        not isinstance(item, Mapping) for item in candidate_entries
    ):
        raise CrossLayerError("candidate release table entries must be objects")
    by_id = {item.get("id"): item for item in candidate_entries}
    if len(by_id) != len(candidate_entries) or any(
        not isinstance(key, str) for key in by_id
    ):
        raise CrossLayerError("candidate release IDs must be unique strings")
    _expect_equal(set(by_id), release_ids, "candidate release IDs mismatch")

    resolved_releases = resolved.get("releases")
    if not isinstance(resolved_releases, list) or any(
        not isinstance(item, Mapping) for item in resolved_releases
    ):
        raise CrossLayerError("resolved releases must be objects")
    resolved_by_id = {item.get("id"): item for item in resolved_releases}
    _expect_equal(set(resolved_by_id), release_ids, "resolved release IDs mismatch")
    for identifier in sorted(release_ids):
        authored = _mapping(releases[identifier], f"policy release {identifier!r}")
        audience = _mapping(
            authored.get("audience"), f"policy release {identifier!r}.audience"
        )
        candidate_row = _mapping(
            by_id[identifier], f"candidate release {identifier!r}"
        )
        _expect_equal(
            candidate_row.get("audience"),
            audience.get("members"),
            f"release {identifier!r} audience mismatch",
        )
    if any(item.get("entry") != model_symbol for item in roles):
        raise CrossLayerError(
            "candidate policy argument roles reference inconsistent reduced-model entries"
        )
