#!/usr/bin/env python3
"""Strict, non-claimable synthetic counterexample-pair fixtures.

The checked-in pair is review data for a fixture, not an SPS witness or public
report.  This module therefore only returns a typed in-memory value and the
canonical digest of the authoring YAML.  It never materializes a derived
artifact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import checkpoint_model


FORMAT_ID = "SPS-Harness-Synthetic-Counterexample-Pair-v1"
CLAIM_BOUNDARY = "NonClaimableFixtureOracle"
SOURCE_CLASS = "SyntheticTestData"
FILENAME = "counterexample-pair.yaml"

_LOWER_HEX = re.compile(r"[0-9a-f]+\Z")
_POLICY_BV = re.compile(r"bv([1-9][0-9]*)\Z")


class CounterexamplePairError(ValueError):
    """A synthetic counterexample-pair contract is invalid."""


@dataclass(frozen=True)
class BitVectorValue:
    width: int
    hex: str


@dataclass(frozen=True)
class BytesValue:
    length: int
    hex: str


SyntheticValue = BitVectorValue | BytesValue


@dataclass(frozen=True)
class PairInputs:
    low_equal: Mapping[str, SyntheticValue]
    high_left: Mapping[str, SyntheticValue]
    high_right: Mapping[str, SyntheticValue]


@dataclass(frozen=True)
class FirstDifference:
    kind: str
    field: str
    id: str | None = None


@dataclass(frozen=True)
class PairExpected:
    bad_state: str
    first_difference: FirstDifference


@dataclass(frozen=True)
class CounterexamplePair:
    path: Path
    format_id: str
    claim_boundary: str
    source_class: str
    entry: str
    coalition: tuple[str, ...]
    inputs: PairInputs
    expected: PairExpected
    canonical_digest: str


def _error(where: str, message: str) -> CounterexamplePairError:
    return CounterexamplePairError(f"{where}: {message}")


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error(where, "expected mapping")
    return value


def _exact_fields(
    value: Mapping[str, Any], required: set[str], optional: set[str], where: str
) -> None:
    actual = set(value)
    allowed = required | optional
    if not required <= actual or not actual <= allowed:
        raise _error(
            where,
            f"wrong fields; missing={sorted(required - actual)}, "
            f"extra={sorted(actual - allowed)}",
        )


def _nonempty_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(where, "expected nonempty string")
    return value


def _positive_integer(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _error(where, "expected positive integer")
    return value


def _string_list(value: Any, where: str, *, canonical: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise _error(where, "expected list")
    if any(not isinstance(item, str) or not item for item in value):
        raise _error(where, "every item must be a nonempty string")
    if canonical and value != sorted(set(value)):
        raise _error(where, "must be sorted and duplicate-free")
    return tuple(value)


def _load_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise _error(str(path), f"cannot read {label}: {error}") from error
    try:
        return checkpoint_model.strict_yaml_load(raw, source=str(path))
    except checkpoint_model.CheckpointError as error:
        raise CounterexamplePairError(str(error)) from error


def _parse_value(value: Any, where: str) -> SyntheticValue:
    envelope = _mapping(value, where)
    if set(envelope) == {"bitvector"}:
        body = _mapping(envelope["bitvector"], f"{where}.bitvector")
        _exact_fields(body, {"width", "hex"}, set(), f"{where}.bitvector")
        width = _positive_integer(body["width"], f"{where}.bitvector.width")
        hexadecimal = body["hex"]
        digits = (width + 3) // 4
        if (
            not isinstance(hexadecimal, str)
            or not _LOWER_HEX.fullmatch(hexadecimal)
            or len(hexadecimal) != digits
        ):
            raise _error(
                f"{where}.bitvector.hex",
                f"expected exactly {digits} lowercase hexadecimal digits",
            )
        unused_high_bits = digits * 4 - width
        if unused_high_bits and int(hexadecimal[0], 16) >= 1 << (4 - unused_high_bits):
            raise _error(f"{where}.bitvector.hex", f"value does not fit bit width {width}")
        return BitVectorValue(width, hexadecimal)
    if set(envelope) == {"bytes"}:
        body = _mapping(envelope["bytes"], f"{where}.bytes")
        _exact_fields(body, {"length", "hex"}, set(), f"{where}.bytes")
        length = _positive_integer(body["length"], f"{where}.bytes.length")
        hexadecimal = body["hex"]
        digits = 2 * length
        if (
            not isinstance(hexadecimal, str)
            or not _LOWER_HEX.fullmatch(hexadecimal)
            or len(hexadecimal) != digits
        ):
            raise _error(
                f"{where}.bytes.hex",
                f"expected exactly {digits} lowercase hexadecimal digits",
            )
        return BytesValue(length, hexadecimal)
    raise _error(where, "value must contain exactly one of 'bitvector' or 'bytes'")


def _parse_assignments(value: Any, where: str) -> Mapping[str, SyntheticValue]:
    mapping = _mapping(value, where)
    parsed: dict[str, SyntheticValue] = {}
    for identifier, raw in mapping.items():
        if (
            not isinstance(identifier, str)
            or not checkpoint_model.STABLE_ID.fullmatch(identifier)
        ):
            raise _error(where, f"malformed stable component identifier {identifier!r}")
        parsed[identifier] = _parse_value(raw, f"{where}.{identifier}")
    return MappingProxyType(dict(sorted(parsed.items())))


def _parse_first_difference(value: Any, where: str) -> FirstDifference:
    mapping = _mapping(value, where)
    _exact_fields(mapping, {"kind", "field"}, {"id"}, where)
    kind = _nonempty_string(mapping["kind"], f"{where}.kind")
    if kind not in checkpoint_model.EVENT_FIELDS:
        raise _error(f"{where}.kind", f"unknown Theta_ct event kind {kind!r}")
    field = _nonempty_string(mapping["field"], f"{where}.field")
    if field not in checkpoint_model.EVENT_FIELDS[kind]:
        raise _error(
            f"{where}.field",
            f"{field!r} is not a field of {kind}; "
            f"expected one of {sorted(checkpoint_model.EVENT_FIELDS[kind])}",
        )
    logical_id = None
    if "id" in mapping:
        if kind not in checkpoint_model.EVENT_ID_KINDS:
            raise _error(
                f"{where}.id",
                "logical IDs apply only to outputs, errors, releases, or bounds",
            )
        logical_id = _nonempty_string(mapping["id"], f"{where}.id")
        if not checkpoint_model.STABLE_ID.fullmatch(logical_id):
            raise _error(f"{where}.id", "malformed stable identifier")
    return FirstDifference(kind, field, logical_id)


def _visibility(value: Any, principals: set[str], where: str) -> Mapping[str, Any]:
    if value == "public":
        return {"world": True, "members": (), "joint": ()}
    if value == "secret":
        return {"world": False, "members": (), "joint": ()}
    mapping = _mapping(value, where)
    _exact_fields(mapping, {"world", "members", "joint"}, set(), where)
    if not isinstance(mapping["world"], bool):
        raise _error(f"{where}.world", "expected boolean")
    members = _string_list(mapping["members"], f"{where}.members", canonical=True)
    raw_joint = mapping["joint"]
    if not isinstance(raw_joint, list):
        raise _error(f"{where}.joint", "expected list")
    joint: list[tuple[str, ...]] = []
    for index, raw_group in enumerate(raw_joint):
        group = _string_list(
            raw_group, f"{where}.joint[{index}]", canonical=True
        )
        if not group:
            raise _error(f"{where}.joint[{index}]", "joint coalition must be nonempty")
        joint.append(group)
    if len(set(joint)) != len(joint):
        raise _error(f"{where}.joint", "contains duplicate coalitions")
    unknown = (set(members) | {member for group in joint for member in group}) - principals
    if unknown:
        raise _error(where, f"references unknown principals {sorted(unknown)}")
    return {"world": mapping["world"], "members": members, "joint": tuple(joint)}


def _is_visible(visibility: Mapping[str, Any], coalition: frozenset[str]) -> bool:
    return bool(
        visibility["world"]
        or coalition.intersection(visibility["members"])
        or any(set(group) <= coalition for group in visibility["joint"])
    )


@dataclass(frozen=True)
class _BitVectorSpec:
    width: int


@dataclass(frozen=True)
class _BytesSpec:
    length: int


_ComponentSpec = _BitVectorSpec | _BytesSpec


def _component_specs(
    policy: Mapping[str, Any], abi: Mapping[str, Any], where: str
) -> Mapping[str, _ComponentSpec]:
    components = _mapping(policy.get("components"), f"{where}.policy.components")
    carriers = _mapping(abi.get("carriers"), f"{where}.abi.carriers")
    roots = _mapping(abi.get("roots"), f"{where}.abi.roots")

    scalar_widths: dict[str, int] = {}
    for identifier, raw_carrier in carriers.items():
        carrier = _mapping(raw_carrier, f"{where}.abi.carriers.{identifier}")
        scalar_widths[identifier] = _positive_integer(
            carrier.get("bit-width"), f"{where}.abi.carriers.{identifier}.bit-width"
        )

    root_lengths: dict[str, int] = {}
    for root_id, raw_root in roots.items():
        root = _mapping(raw_root, f"{where}.abi.roots.{root_id}")
        if "input" not in root:
            continue
        input_id = _nonempty_string(root["input"], f"{where}.abi.roots.{root_id}.input")
        if input_id in root_lengths:
            raise _error(
                f"{where}.abi.roots.{root_id}.input",
                f"component {input_id!r} is bound by more than one root",
            )
        if root.get("initialization") != "initialized":
            raise _error(
                f"{where}.abi.roots.{root_id}.initialization",
                "input byte roots must be initialized",
            )
        root_lengths[input_id] = _positive_integer(
            root.get("extent-bytes"), f"{where}.abi.roots.{root_id}.extent-bytes"
        )

    overlap = set(scalar_widths) & set(root_lengths)
    if overlap:
        raise _error(
            where,
            f"components have both scalar and root ABI bindings: {sorted(overlap)}",
        )
    bound = set(scalar_widths) | set(root_lengths)
    if set(components) != bound:
        raise _error(
            where,
            "policy components and ABI scalar/root inputs differ; "
            f"missing_bindings={sorted(set(components) - bound)}, "
            f"extra_bindings={sorted(bound - set(components))}",
        )

    specs: dict[str, _ComponentSpec] = {}
    for identifier, raw_component in components.items():
        component = _mapping(raw_component, f"{where}.policy.components.{identifier}")
        policy_type = component.get("type")
        if identifier in scalar_widths:
            match = _POLICY_BV.fullmatch(policy_type) if isinstance(policy_type, str) else None
            if match is None:
                raise _error(
                    f"{where}.policy.components.{identifier}.type",
                    "scalar ABI carriers require a bvN policy type",
                )
            policy_width = int(match.group(1))
            if policy_width != scalar_widths[identifier]:
                raise _error(
                    f"{where}.abi.carriers.{identifier}.bit-width",
                    f"width {scalar_widths[identifier]} disagrees with policy width {policy_width}",
                )
            specs[identifier] = _BitVectorSpec(policy_width)
        else:
            if policy_type != "bytes":
                raise _error(
                    f"{where}.policy.components.{identifier}.type",
                    "ABI root inputs require the 'bytes' policy type",
                )
            specs[identifier] = _BytesSpec(root_lengths[identifier])
    return MappingProxyType(specs)


def _validate_assignments(
    inputs: PairInputs,
    policy: Mapping[str, Any],
    abi: Mapping[str, Any],
    coalition: tuple[str, ...],
    where: str,
) -> None:
    principals_raw = policy.get("principals")
    principals = set(_string_list(principals_raw, f"{where}.policy.principals"))
    if len(principals) != len(principals_raw):
        raise _error(f"{where}.policy.principals", "contains duplicates")
    coalition_set = frozenset(coalition)
    unknown = coalition_set - principals
    if unknown:
        raise _error(f"{where}.coalition", f"contains undeclared principals {sorted(unknown)}")

    adversaries = _mapping(policy.get("adversaries"), f"{where}.policy.adversaries")
    maxima_raw = adversaries.get("maximal")
    if not isinstance(maxima_raw, list) or not maxima_raw:
        raise _error(f"{where}.policy.adversaries.maximal", "expected nonempty list")
    maxima: list[set[str]] = []
    for index, raw in enumerate(maxima_raw):
        maximum = set(
            _string_list(raw, f"{where}.policy.adversaries.maximal[{index}]")
        )
        if not maximum <= principals:
            raise _error(
                f"{where}.policy.adversaries.maximal[{index}]",
                f"contains undeclared principals {sorted(maximum - principals)}",
            )
        maxima.append(maximum)
    if not any(coalition_set <= maximum for maximum in maxima):
        raise _error(
            f"{where}.coalition",
            "is not in the downward closure of a maximal adversary coalition",
        )

    components = _mapping(policy.get("components"), f"{where}.policy.components")
    visible: set[str] = set()
    for identifier, raw_component in components.items():
        component = _mapping(raw_component, f"{where}.policy.components.{identifier}")
        visibility = _visibility(
            component.get("visibility"),
            principals,
            f"{where}.policy.components.{identifier}.visibility",
        )
        if _is_visible(visibility, coalition_set):
            visible.add(identifier)
    high = set(components) - visible

    low_ids = set(inputs.low_equal)
    left_ids = set(inputs.high_left)
    right_ids = set(inputs.high_right)
    if low_ids != visible:
        raise _error(
            f"{where}.inputs.low_equal",
            "must exactly cover coalition-visible policy components; "
            f"missing={sorted(visible - low_ids)}, extra={sorted(low_ids - visible)}",
        )
    if left_ids != high:
        raise _error(
            f"{where}.inputs.high_left",
            "must exactly cover coalition-hidden policy components; "
            f"missing={sorted(high - left_ids)}, extra={sorted(left_ids - high)}",
        )
    if right_ids != high:
        raise _error(
            f"{where}.inputs.high_right",
            "must exactly cover coalition-hidden policy components; "
            f"missing={sorted(high - right_ids)}, extra={sorted(right_ids - high)}",
        )

    specs = _component_specs(policy, abi, where)
    for section_name, assignments in (
        ("low_equal", inputs.low_equal),
        ("high_left", inputs.high_left),
        ("high_right", inputs.high_right),
    ):
        for identifier, assigned in assignments.items():
            spec = specs[identifier]
            item_where = f"{where}.inputs.{section_name}.{identifier}"
            if isinstance(spec, _BitVectorSpec):
                if not isinstance(assigned, BitVectorValue):
                    raise _error(item_where, "scalar ABI carrier requires a bitvector value")
                if assigned.width != spec.width:
                    raise _error(
                        f"{item_where}.bitvector.width",
                        f"expected ABI width {spec.width}, got {assigned.width}",
                    )
            else:
                if not isinstance(assigned, BytesValue):
                    raise _error(item_where, "ABI root input requires a bytes value")
                if assigned.length != spec.length:
                    raise _error(
                        f"{item_where}.bytes.length",
                        f"expected ABI extent {spec.length}, got {assigned.length}",
                    )

    if not high:
        raise _error(f"{where}.inputs", "counterexample pair requires a High component")
    if all(inputs.high_left[item] == inputs.high_right[item] for item in high):
        raise _error(
            f"{where}.inputs",
            "at least one High component must differ between high_left and high_right",
        )


def load_counterexample_pair(
    path: Path,
    snapshot: checkpoint_model.SnapshotV3,
    *,
    policy_path: Path | None = None,
    abi_path: Path | None = None,
) -> CounterexamplePair:
    """Load and validate one fixed-name sibling counterexample pair."""

    source_path = Path(path)
    if source_path.is_symlink():
        raise _error(str(source_path), "pair sidecar must not be a symlink")
    path = source_path.resolve()
    if path.name != FILENAME:
        raise _error(str(path), f"pair sidecar must be named {FILENAME}")
    if path.parent != snapshot.path.resolve().parent:
        raise _error(str(path), "pair must be a sibling of its snapshot.yaml")
    policy_path = (
        Path(policy_path).resolve()
        if policy_path is not None
        else path.parent / "policy.sps.yaml"
    )
    abi_path = (
        Path(abi_path).resolve()
        if abi_path is not None
        else path.parent / "abi.sps.yaml"
    )
    value = _load_yaml(path, "counterexample pair")
    policy = _load_yaml(policy_path, "policy")
    abi = _load_yaml(abi_path, "ABI")
    where = str(path)

    _exact_fields(
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
        set(),
        where,
    )
    if value["format_id"] != FORMAT_ID:
        raise _error(f"{where}.format_id", f"must be {FORMAT_ID!r}")
    if value["claim_boundary"] != CLAIM_BOUNDARY:
        raise _error(f"{where}.claim_boundary", f"must be {CLAIM_BOUNDARY!r}")
    if value["source_class"] != SOURCE_CLASS:
        raise _error(f"{where}.source_class", f"must be {SOURCE_CLASS!r}")

    entry = _nonempty_string(value["entry"], f"{where}.entry")
    policy_entry = policy.get("entry")
    abi_entry = _mapping(abi.get("entry"), f"{where}.abi.entry").get("id")
    expected_entry = snapshot.entry
    if entry != expected_entry or policy_entry != expected_entry or abi_entry != expected_entry:
        raise _error(
            f"{where}.entry",
            "pair, policy, ABI, and snapshot entries must agree; "
            f"pair={entry!r}, policy={policy_entry!r}, ABI={abi_entry!r}, "
            f"snapshot={expected_entry!r}",
        )
    coalition = _string_list(value["coalition"], f"{where}.coalition", canonical=True)

    raw_inputs = _mapping(value["inputs"], f"{where}.inputs")
    _exact_fields(
        raw_inputs,
        {"low_equal", "high_left", "high_right"},
        set(),
        f"{where}.inputs",
    )
    inputs = PairInputs(
        low_equal=_parse_assignments(raw_inputs["low_equal"], f"{where}.inputs.low_equal"),
        high_left=_parse_assignments(raw_inputs["high_left"], f"{where}.inputs.high_left"),
        high_right=_parse_assignments(raw_inputs["high_right"], f"{where}.inputs.high_right"),
    )

    raw_expected = _mapping(value["expected"], f"{where}.expected")
    _exact_fields(
        raw_expected,
        {"bad_state", "first_difference"},
        set(),
        f"{where}.expected",
    )
    bad_state = _nonempty_string(raw_expected["bad_state"], f"{where}.expected.bad_state")
    if not checkpoint_model.STABLE_ID.fullmatch(bad_state):
        raise _error(f"{where}.expected.bad_state", "malformed stable identifier")
    first_difference = _parse_first_difference(
        raw_expected["first_difference"], f"{where}.expected.first_difference"
    )

    if snapshot.final.status != "Counterexample":
        raise _error(where, "pair is legal only for an expected Counterexample snapshot")
    first_bad = tuple(event for event in snapshot.final.events if event.first_bad)
    if len(first_bad) != 1:
        raise _error(where, "Counterexample snapshot must have exactly one first_bad event")
    snapshot_difference = FirstDifference(
        first_bad[0].kind, first_bad[0].field, first_bad[0].id
    )
    if bad_state != snapshot.final.bad_state:
        raise _error(
            f"{where}.expected.bad_state",
            f"must match snapshot bad_state {snapshot.final.bad_state!r}",
        )
    if first_difference != snapshot_difference:
        raise _error(
            f"{where}.expected.first_difference",
            "must exactly match the snapshot's sole first_bad event; "
            f"pair={first_difference!r}, snapshot={snapshot_difference!r}",
        )

    _validate_assignments(inputs, policy, abi, coalition, where)
    return CounterexamplePair(
        path=path,
        format_id=FORMAT_ID,
        claim_boundary=CLAIM_BOUNDARY,
        source_class=SOURCE_CLASS,
        entry=entry,
        coalition=coalition,
        inputs=inputs,
        expected=PairExpected(bad_state, first_difference),
        canonical_digest=checkpoint_model.canonical_digest(value),
    )


def load_fixture_pair(
    snapshot: checkpoint_model.SnapshotV3,
) -> CounterexamplePair | None:
    """Enforce exactly one pair for Counterexample and none for other statuses."""

    path = snapshot.path.resolve().parent / FILENAME
    exists = path.exists()
    if snapshot.final.status == "Counterexample":
        if not path.is_file():
            raise _error(str(snapshot.path), f"Counterexample requires sibling {FILENAME}")
        if path.is_symlink():
            raise _error(str(path), "pair sidecar must not be a symlink")
        return load_counterexample_pair(path, snapshot)
    if exists:
        raise _error(
            str(path),
            f"{snapshot.final.status} snapshot must not have a synthetic counterexample pair",
        )
    return None


# Concise public alias for callers that already know they are loading a pair.
load_pair = load_counterexample_pair
