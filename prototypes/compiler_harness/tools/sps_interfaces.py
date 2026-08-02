#!/usr/bin/env python3
"""Consume and verify the SPS-owned Rev4.1 machine interfaces.

SPS owns serialized field sets, tagged-union shapes, literals, scalar types,
and canonical field order.  The harness vendors a digest-locked distribution
and derives its validators from ``interface-registry.json``.  Mathematical and
cross-field obligations remain explicit semantic checks identified by stable
``XF-*`` rule IDs.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


HARNESS_ROOT = Path(__file__).resolve().parent.parent
VENDOR_ROOT = HARNESS_ROOT / "contracts" / "vendor" / "sps-rev4.1"
VENDOR_MANIFEST = VENDOR_ROOT / "upstream-manifest.json"
LOCK_PATH = HARNESS_ROOT / "contracts" / "sps-interface.lock.json"
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$")
HEX_RE = re.compile(r"^[0-9a-f]{64}$")
BYTES_RE = re.compile(r"^(?:[0-9a-f]{2})*$")


class InterfaceError(ValueError):
    pass


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except UnicodeEncodeError as error:
        raise InterfaceError("invalid Unicode scalar value") from error


def strict_load(raw: bytes) -> Any:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise InterfaceError("UTF-8 BOM is forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InterfaceError("invalid UTF-8") from error

    def pairs(rows: list[tuple[str, Any]]) -> OrderedDict[str, Any]:
        result: OrderedDict[str, Any] = OrderedDict()
        for key, value in rows:
            if key in result:
                raise InterfaceError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def bad_constant(value: str) -> Any:
        raise InterfaceError(f"forbidden numeric constant: {value}")

    def bad_float(_: str) -> Any:
        raise InterfaceError("floating-point JSON numbers are forbidden")

    try:
        return json.loads(
            text,
            object_pairs_hook=pairs,
            parse_float=bad_float,
            parse_constant=bad_constant,
        )
    except json.JSONDecodeError as error:
        raise InterfaceError(f"invalid JSON: {error}") from error


def require_canonical(raw: bytes) -> Any:
    value = strict_load(raw)
    if canonical_bytes(value) != raw:
        raise InterfaceError("bytes are not canonical SPS interface JSON")
    return value


def _schema_documents(distribution: Path) -> dict[str, Any]:
    documents: dict[str, Any] = {}
    for path in (distribution / "schemas").glob("*.json"):
        value = require_canonical(path.read_bytes())
        identifier = value.get("$id") if isinstance(value, dict) else None
        if not isinstance(identifier, str) or identifier in documents:
            raise InterfaceError(f"missing or duplicate schema $id in {path.name}")
        documents[identifier] = value
    return documents


def _resolve_schema_ref(documents: dict[str, Any], reference: str) -> Any:
    base, separator, fragment = reference.partition("#")
    if base not in documents:
        raise InterfaceError(f"external or missing schema document: {base}")
    target = documents[base]
    if not separator or fragment == "":
        return target
    if not fragment.startswith("/"):
        raise InterfaceError(f"unsupported or missing schema fragment: {reference}")
    for encoded in fragment[1:].split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, dict) or token not in target:
            raise InterfaceError(f"missing schema fragment target: {reference}")
        target = target[token]
    return target


def _schema_type_matches(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def _schema_equal_key(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _validate_json_schema(
    value: Any,
    schema: Any,
    documents: dict[str, Any],
    where: str = "$",
) -> None:
    """Execute the closed Draft-2020-12 subset emitted by the SPS builder.

    This layer is intentionally independent of the registry validator below.
    Rejecting an unsupported schema keyword makes schema evolution fail closed
    until this consumer is updated.
    """

    if schema is True:
        return
    if schema is False:
        raise InterfaceError(f"{where}: rejected by false JSON Schema")
    if not isinstance(schema, dict):
        raise InterfaceError(f"{where}: malformed JSON Schema node")
    supported = {
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "title",
        "type",
        "pattern",
        "minimum",
        "const",
        "enum",
        "properties",
        "required",
        "additionalProperties",
        "oneOf",
        "items",
        "prefixItems",
        "minItems",
        "maxItems",
        "uniqueItems",
    }
    unknown = sorted(
        key for key in schema if key not in supported and not key.startswith("x-sps-")
    )
    if unknown:
        raise InterfaceError(
            f"{where}: unsupported Draft-2020-12 schema keywords {unknown}"
        )
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str):
            raise InterfaceError(f"{where}: malformed JSON Schema $ref")
        _validate_json_schema(
            value, _resolve_schema_ref(documents, reference), documents, where
        )

    if "oneOf" in schema:
        alternatives = schema["oneOf"]
        if not isinstance(alternatives, list) or not alternatives:
            raise InterfaceError(f"{where}: malformed JSON Schema oneOf")
        matches = 0
        for alternative in alternatives:
            try:
                _validate_json_schema(value, alternative, documents, where)
            except InterfaceError:
                continue
            matches += 1
        if matches != 1:
            raise InterfaceError(
                f"{where}: JSON Schema oneOf matched {matches} alternatives"
            )

    if "const" in schema and (
        value != schema["const"] or type(value) is not type(schema["const"])
    ):
        raise InterfaceError(f"{where}: JSON Schema const mismatch")
    if "enum" in schema:
        choices = schema["enum"]
        if not isinstance(choices, list) or value not in choices:
            raise InterfaceError(f"{where}: JSON Schema enum mismatch")

    expected_type = schema.get("type")
    if expected_type is not None:
        if not isinstance(expected_type, str) or not _schema_type_matches(
            value, expected_type
        ):
            raise InterfaceError(
                f"{where}: JSON Schema expected type {expected_type!r}"
            )

    if isinstance(value, dict) and (
        expected_type == "object"
        or "properties" in schema
        or "required" in schema
        or "additionalProperties" in schema
    ):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise InterfaceError(f"{where}: malformed object JSON Schema")
        missing = [name for name in required if name not in value]
        if missing:
            raise InterfaceError(f"{where}: JSON Schema missing required {missing}")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise InterfaceError(
                    f"{where}: JSON Schema additional properties {extra}"
                )
        for name, member in value.items():
            if name in properties:
                _validate_json_schema(
                    member, properties[name], documents, f"{where}.{name}"
                )

    if isinstance(value, list) and (
        expected_type == "array"
        or any(
            key in schema
            for key in ("items", "prefixItems", "minItems", "maxItems", "uniqueItems")
        )
    ):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if minimum is not None and len(value) < minimum:
            raise InterfaceError(f"{where}: JSON Schema minItems violation")
        if maximum is not None and len(value) > maximum:
            raise InterfaceError(f"{where}: JSON Schema maxItems violation")
        if schema.get("uniqueItems"):
            encoded = [_schema_equal_key(item) for item in value]
            if len(encoded) != len(set(encoded)):
                raise InterfaceError(f"{where}: JSON Schema uniqueItems violation")
        prefix = schema.get("prefixItems", [])
        if not isinstance(prefix, list):
            raise InterfaceError(f"{where}: malformed JSON Schema prefixItems")
        for index, item_schema in enumerate(prefix):
            if index < len(value):
                _validate_json_schema(
                    value[index], item_schema, documents, f"{where}[{index}]"
                )
        item_schema = schema.get("items")
        if item_schema is not None:
            for index in range(len(prefix), len(value)):
                _validate_json_schema(
                    value[index], item_schema, documents, f"{where}[{index}]"
                )

    if isinstance(value, str) and "pattern" in schema:
        pattern = schema["pattern"]
        if not isinstance(pattern, str) or re.search(pattern, value) is None:
            raise InterfaceError(f"{where}: JSON Schema pattern mismatch")
    if isinstance(value, int) and not isinstance(value, bool) and "minimum" in schema:
        if value < schema["minimum"]:
            raise InterfaceError(f"{where}: JSON Schema minimum violation")


def validate_schema_root(
    value: Any, root_type: str, distribution: Path
) -> None:
    documents = _schema_documents(distribution)
    candidates = [
        document
        for document in documents.values()
        if isinstance(document, dict)
        and isinstance(document.get("$defs"), dict)
        and root_type in document["$defs"]
    ]
    if len(candidates) != 1:
        raise InterfaceError(
            f"JSON Schema root {root_type!r} resolves in {len(candidates)} bundles"
        )
    _validate_json_schema(value, candidates[0]["$defs"][root_type], documents)


# Private mirror of the prose-defined payload grammar in
# SPS/interfaces/rev4.1/build_interfaces.py.  Wire records, unions, enums, and
# literals continue to come from Interface Registry metadata; these predicates
# only close the opaque canonical payloads carried inside digest envelopes.
_SPS_POLICY_EXPR_FIELDS = {
    "BoolLiteral": ["tag", "value", "sort"],
    "NatLiteral": ["tag", "value", "max", "sort"],
    "BVLiteral": ["tag", "width", "exactWidthBits", "sort"],
    "FiniteTagLiteral": ["tag", "domainId", "memberId", "sort"],
    "ComponentRef": ["tag", "componentId", "snapshot", "sort"],
    "PublicBoundRef": ["tag", "boundId", "sort"],
    "OccurrenceCounterRef": ["tag", "releaseOrTimingId", "sort"],
    "RelationFieldRef": ["tag", "side", "fieldPath", "sort"],
    "TupleExpr": ["tag", "fieldExprs", "sort"],
    "Project": ["tag", "tupleExpr", "fieldIndex", "sort"],
    "Ite": ["tag", "condition", "then", "else", "sort"],
    "Extract": ["tag", "operand", "highInclusive", "lowInclusive", "sort"],
    "ZeroExtend": ["tag", "operand", "resultWidth", "sort"],
    "SignExtend": ["tag", "operand", "resultWidth", "sort"],
    "TruncateLow": ["tag", "operand", "resultWidth", "sort"],
    "ArgMax": [
        "tag", "elements", "elementSignedness", "iterationOrder",
        "tieRule", "resultWidth", "sort",
    ],
}
for _sps_tag in ("Not", "BVNot"):
    _SPS_POLICY_EXPR_FIELDS[_sps_tag] = ["tag", "operand", "sort"]
for _sps_tag in ("And", "Or"):
    _SPS_POLICY_EXPR_FIELDS[_sps_tag] = ["tag", "operands", "sort"]
for _sps_tag in (
    "Xor", "BVAnd", "BVOr", "BVXor", "BVAddWrap", "BVSubWrap",
    "BVMulWrap", "BoolEqual", "BVEqual", "TagEqual", "TupleEqual",
):
    _SPS_POLICY_EXPR_FIELDS[_sps_tag] = ["tag", "lhs", "rhs", "sort"]
_SPS_POLICY_EXPR_FIELDS["Concat"] = ["tag", "high", "low", "sort"]
for _sps_tag in ("NatAddChecked", "NatMulChecked"):
    _SPS_POLICY_EXPR_FIELDS[_sps_tag] = [
        "tag", "lhs", "rhs", "resultMax", "sort"
    ]
_SPS_POLICY_EXPR_FIELDS["BVCompare"] = [
    "tag", "predicate", "signedness", "lhs", "rhs", "sort"
]
_SPS_POLICY_EXPR_FIELDS["NatCompare"] = [
    "tag", "predicate", "lhs", "rhs", "sort"
]


def _sps_typed_nat(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _sps_typed_pos(value: Any) -> bool:
    return _sps_typed_nat(value) and value > 0


def _sps_typed_id(value: Any) -> bool:
    return isinstance(value, str) and ID_RE.fullmatch(value) is not None


def _sps_typed_digest(value: Any) -> bool:
    return isinstance(value, str) and HEX_RE.fullmatch(value) is not None


def _sps_typed_tag(value: Any, tag: str) -> bool:
    return isinstance(value, dict) and list(value) == ["tag"] and value["tag"] == tag


def _sps_typed_args(value: Any, tag: str, predicates: list[Any]) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["tag", "args"]
        and value["tag"] == tag and isinstance(value["args"], list)
        and len(value["args"]) == len(predicates)
        and all(predicate(item) for predicate, item in zip(predicates, value["args"]))
    )


def _sps_typed_option(value: Any, predicate: Any) -> bool:
    return _sps_typed_tag(value, "None") or (
        isinstance(value, dict) and list(value) == ["tag", "value"]
        and value["tag"] == "Some" and predicate(value["value"])
    )


def _sps_typed_id_list(value: Any, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list) and (not nonempty or bool(value))
        and all(_sps_typed_id(item) for item in value)
        and value == sorted(value) and len(value) == len(set(value))
    )


def _sps_typed_canonical_unique_list(value: Any, *, nonempty: bool = False) -> bool:
    if not isinstance(value, list) or (nonempty and not value):
        return False
    encoded = [canonical_bytes(item) for item in value]
    return encoded == sorted(encoded) and len(encoded) == len(set(encoded))


def _sps_typed_unique_list(value: Any, *, nonempty: bool = False) -> bool:
    if not isinstance(value, list) or (nonempty and not value):
        return False
    encoded = [canonical_bytes(item) for item in value]
    return len(encoded) == len(set(encoded))


def _sps_typed_map_rows(rows: Any, key_predicate: Any, value_predicate: Any) -> bool:
    if not isinstance(rows, list):
        return False
    encoded_keys: list[bytes] = []
    for row in rows:
        if (
            not isinstance(row, dict) or list(row) != ["key", "value"]
            or not key_predicate(row["key"]) or not value_predicate(row["value"])
        ):
            return False
        encoded_keys.append(canonical_bytes(row["key"]))
    return encoded_keys == sorted(encoded_keys) and len(encoded_keys) == len(set(encoded_keys))


def _sps_typed_policy_sort(value: Any) -> bool:
    if _sps_typed_tag(value, "Bool"):
        return True
    if _sps_typed_args(value, "Nat", [_sps_typed_nat]) or _sps_typed_args(value, "BV", [_sps_typed_pos]):
        return True
    if _sps_typed_args(value, "FiniteTag", [_sps_typed_id]):
        return True
    return _sps_typed_args(value, "Tuple", [
        lambda items: isinstance(items, list) and bool(items)
        and all(_sps_typed_policy_sort(item) for item in items)
    ])


def _sps_typed_nat_sort(value: Any) -> bool:
    return _sps_typed_args(value, "Nat", [_sps_typed_nat])


def _sps_typed_relation_field_path(value: Any) -> bool:
    if any(_sps_typed_tag(value, tag) for tag in [
        "ContractInputUnitV2", "ContractOutcomeV2", "CouplingOccurrenceV2",
        "CouplingChoiceV2",
    ]):
        return True
    nested = lambda item: isinstance(item, list) and all(_sps_typed_nat(part) for part in item)
    whole = lambda item: _sps_typed_tag(item, "WholeValueV2")
    return any([
        _sps_typed_args(value, "ContractArgumentV2", [_sps_typed_nat, nested, whole]),
        _sps_typed_args(value, "ContractPreStateV2", [nested]),
        _sps_typed_args(value, "ContractPreEffectByteV2", [_sps_typed_nat, _sps_typed_nat]),
        _sps_typed_args(value, "ContractResultV2", [nested]),
        _sps_typed_args(value, "ContractPostStateV2", [nested]),
        _sps_typed_args(value, "ContractPostEffectByteV2", [_sps_typed_nat, _sps_typed_nat]),
        _sps_typed_args(value, "ContractMetadataV2", [_sps_typed_id, nested]),
        _sps_typed_args(value, "ContractFailurePayloadV2", [_sps_typed_id, nested]),
    ])


def _sps_typed_policy_expr(value: Any) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("tag"), str):
        return False
    tag = value["tag"]
    if (
        tag not in _SPS_POLICY_EXPR_FIELDS
        or list(value) != _SPS_POLICY_EXPR_FIELDS[tag]
    ):
        return False
    if not _sps_typed_policy_sort(value["sort"]):
        return False
    expression = _sps_typed_policy_expr
    if tag == "BoolLiteral":
        return isinstance(value["value"], bool)
    if tag == "NatLiteral":
        return _sps_typed_nat(value["value"]) and _sps_typed_nat(value["max"]) and value["value"] <= value["max"]
    if tag == "BVLiteral":
        bits = value["exactWidthBits"]
        return _sps_typed_pos(value["width"]) and isinstance(bits, str) and re.fullmatch(r"[01]+", bits) is not None and len(bits) == value["width"]
    if tag == "FiniteTagLiteral":
        return _sps_typed_id(value["domainId"]) and _sps_typed_id(value["memberId"])
    if tag == "ComponentRef":
        return _sps_typed_id(value["componentId"]) and value["snapshot"] == "EntryInitial"
    if tag == "PublicBoundRef":
        return _sps_typed_id(value["boundId"])
    if tag == "OccurrenceCounterRef":
        return _sps_typed_id(value["releaseOrTimingId"])
    if tag == "RelationFieldRef":
        return value["side"] in {"Left", "Right"} and _sps_typed_relation_field_path(value["fieldPath"])
    if tag == "TupleExpr":
        return isinstance(value["fieldExprs"], list) and bool(value["fieldExprs"]) and all(expression(item) for item in value["fieldExprs"])
    if tag == "Project":
        return expression(value["tupleExpr"]) and _sps_typed_nat(value["fieldIndex"])
    if tag == "Ite":
        return all(expression(value[field]) for field in ["condition", "then", "else"])
    if tag in {"Not", "BVNot"}:
        return expression(value["operand"])
    if tag in {"And", "Or"}:
        return isinstance(value["operands"], list) and bool(value["operands"]) and all(expression(item) for item in value["operands"])
    if tag in {
        "Xor", "BVAnd", "BVOr", "BVXor", "BVAddWrap", "BVSubWrap",
        "BVMulWrap", "BoolEqual", "BVEqual", "TagEqual", "TupleEqual",
    }:
        return expression(value["lhs"]) and expression(value["rhs"])
    if tag == "Concat":
        return expression(value["high"]) and expression(value["low"])
    if tag == "BVCompare":
        return (
            value["predicate"] in {"LT", "LE", "GT", "GE"}
            and value["signedness"] in {"Unsigned", "SignedTwosComplement"}
            and expression(value["lhs"]) and expression(value["rhs"])
        )
    if tag == "NatCompare":
        return value["predicate"] in {"LT", "LE", "GT", "GE", "EQ", "NE"} and expression(value["lhs"]) and expression(value["rhs"])
    if tag == "Extract":
        return expression(value["operand"]) and _sps_typed_nat(value["highInclusive"]) and _sps_typed_nat(value["lowInclusive"])
    if tag in {"ZeroExtend", "SignExtend", "TruncateLow"}:
        return expression(value["operand"]) and _sps_typed_pos(value["resultWidth"])
    if tag in {"NatAddChecked", "NatMulChecked"}:
        return expression(value["lhs"]) and expression(value["rhs"]) and _sps_typed_nat(value["resultMax"])
    if tag == "ArgMax":
        return (
            isinstance(value["elements"], list) and bool(value["elements"])
            and all(expression(item) for item in value["elements"])
            and value["elementSignedness"] in {"Unsigned", "SignedTwosComplement"}
            and value["iterationOrder"] == "IncreasingIndex"
            and value["tieRule"] == "LowestIndex" and _sps_typed_pos(value["resultWidth"])
        )
    return False


def _sps_typed_manifest_value_type(value: Any) -> bool:
    if _sps_typed_tag(value, "BoolValueV2"):
        return True
    if _sps_typed_args(value, "BVValueV2", [_sps_typed_pos]) or _sps_typed_args(value, "FixedBytesValueV2", [_sps_typed_pos]):
        return True
    return _sps_typed_args(value, "TupleValueV2", [
        lambda fields: isinstance(fields, list) and bool(fields)
        and all(
            isinstance(field, list) and len(field) == 2 and _sps_typed_id(field[0])
            and _sps_typed_manifest_value_type(field[1])
            for field in fields
        )
        and len({field[0] for field in fields}) == len(fields)
    ])


def _sps_typed_return_class(value: Any) -> bool:
    return (
        _sps_typed_tag(value, "NormalVoid") or _sps_typed_tag(value, "NormalValue")
        or _sps_typed_args(value, "DeclaredFailure", [_sps_typed_id])
    )


def _sps_typed_argument_role(value: Any) -> bool:
    return any(_sps_typed_args(value, tag, [_sps_typed_id]) for tag in [
        "ComponentArgumentV2", "PointerRootArgumentV2",
        "PublicConfigurationArgumentV2",
    ])


def _sps_typed_bit_encoding(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["bitWidth", "byteWidth", "byteOrder", "highPaddingBits", "signedness"]
        and _sps_typed_pos(value["bitWidth"]) and _sps_typed_pos(value["byteWidth"])
        and value["byteOrder"] in {"LittleEndian", "BigEndian"}
        and _sps_typed_nat(value["highPaddingBits"]) and value["highPaddingBits"] < 8
        and value["signedness"] in {"Unsigned", "SignedTwosComplement", "NotNumeric"}
        and value["byteWidth"] == (value["bitWidth"] + 7) // 8
        and value["highPaddingBits"] == 8 * value["byteWidth"] - value["bitWidth"]
    )


def _sps_typed_root_slice(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["rootId", "byteOffset", "byteWidth"]
        and _sps_typed_id(value["rootId"]) and _sps_typed_nat(value["byteOffset"])
        and _sps_typed_pos(value["byteWidth"])
    )


def _sps_typed_scalar_type(value: Any) -> bool:
    return any(_sps_typed_tag(value, tag) for tag in ["I1", "I8", "I16", "I32", "I64", "F32", "F64"])


def _sps_typed_carrier(value: Any) -> bool:
    return any([
        _sps_typed_args(value, "ScalarArgumentCarrierV2", [_sps_typed_id, _sps_typed_nat, _sps_typed_scalar_type, _sps_typed_bit_encoding]),
        _sps_typed_args(value, "RootSliceCarrierV2", [_sps_typed_id, _sps_typed_root_slice, _sps_typed_bit_encoding, lambda item: item == "EntryInitial"]),
        _sps_typed_args(value, "GlobalSliceCarrierV2", [_sps_typed_id, _sps_typed_id, _sps_typed_nat, _sps_typed_pos, _sps_typed_bit_encoding, lambda item: item == "EntryInitial"]),
    ])


def _sps_typed_visibility(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["worldVisible", "memberVisible", "minimallyJointVisible"]
        and _sps_typed_id_list(value["worldVisible"])
        and _sps_typed_map_rows(value["memberVisible"], _sps_typed_id, _sps_typed_id_list)
        and isinstance(value["minimallyJointVisible"], list)
        and _sps_typed_canonical_unique_list(value["minimallyJointVisible"])
        and all(
            isinstance(row, list) and len(row) == 2
            and _sps_typed_id_list(row[0], nonempty=True) and _sps_typed_id(row[1])
            for row in value["minimallyJointVisible"]
        )
    )


def _sps_policy_payload_is_typed(
    value: Any, lint_classes: list[str] | tuple[str, ...]
) -> bool:
    def component(component_value: Any) -> bool:
        return (
            isinstance(component_value, dict)
            and list(component_value) == ["valueType", "lifecycle", "applicableEntries"]
            and _sps_typed_manifest_value_type(component_value["valueType"])
            and component_value["lifecycle"] in {"EntryInput", "PersistentState", "DerivedPublic"}
            and _sps_typed_id_list(component_value["applicableEntries"], nonempty=True)
        )

    def entry(entry_value: Any) -> bool:
        return (
            isinstance(entry_value, dict)
            and list(entry_value) == ["llvmSymbol", "argumentRoles", "allowedReturnClasses"]
            and isinstance(entry_value["llvmSymbol"], str)
            and isinstance(entry_value["argumentRoles"], list)
            and all(_sps_typed_argument_role(item) for item in entry_value["argumentRoles"])
            and isinstance(entry_value["allowedReturnClasses"], list)
            and bool(entry_value["allowedReturnClasses"])
            and _sps_typed_canonical_unique_list(entry_value["allowedReturnClasses"])
            and all(_sps_typed_return_class(item) for item in entry_value["allowedReturnClasses"])
        )

    return (
        _sps_typed_digest(value["policyId"])
        and _sps_typed_id_list(value["principals"], nonempty=True)
        and _sps_typed_id_list(value["hosts"], nonempty=True)
        and _sps_typed_visibility(value["hostVisibility"])
        and isinstance(value["maximalAdversaryCoalitions"], list)
        and _sps_typed_canonical_unique_list(value["maximalAdversaryCoalitions"], nonempty=True)
        and all(_sps_typed_id_list(coalition, nonempty=True) for coalition in value["maximalAdversaryCoalitions"])
        and _sps_typed_map_rows(value["components"], _sps_typed_id, component)
        and all(_sps_typed_visibility(value[field]) for field in ["componentVisibility", "outputVisibility", "errorVisibility"])
        and _sps_typed_map_rows(value["entries"], _sps_typed_id, entry) and bool(value["entries"])
        and _sps_typed_map_rows(value["publicBounds"], _sps_typed_id, _sps_typed_policy_expr)
        and isinstance(value["preconditions"], list) and all(_sps_typed_policy_expr(item) for item in value["preconditions"])
        and _sps_typed_map_rows(value["publicAliasTopologyIds"], _sps_typed_id, _sps_typed_id_list)
        and _sps_typed_map_rows(value["expectedVariableAssertions"], _sps_typed_id, lambda item:
            isinstance(item, dict) and list(item) == ["entry", "coalition", "component"]
            and _sps_typed_id(item["entry"]) and _sps_typed_id_list(item["coalition"])
            and _sps_typed_id(item["component"]))
        and _sps_typed_map_rows(value["allocaSizeBindings"], _sps_typed_id, _sps_typed_policy_expr)
        and isinstance(value["releasePolicyReviewConfig"], dict)
        and list(value["releasePolicyReviewConfig"]) == ["capacityWarningThresholdBits", "enabledLintSet", "versionAndSemantics"]
        and isinstance(value["releasePolicyReviewConfig"]["capacityWarningThresholdBits"], dict)
        and list(value["releasePolicyReviewConfig"]["capacityWarningThresholdBits"]) == ["numerator", "denominator"]
        and _sps_typed_nat(value["releasePolicyReviewConfig"]["capacityWarningThresholdBits"]["numerator"])
        and _sps_typed_pos(value["releasePolicyReviewConfig"]["capacityWarningThresholdBits"]["denominator"])
        and value["releasePolicyReviewConfig"]["enabledLintSet"] == list(lint_classes)
        and _sps_typed_digest(value["releasePolicyReviewConfig"]["versionAndSemantics"])
        and _sps_typed_map_rows(value["entryPlacement"], _sps_typed_id, _sps_typed_id)
        and _sps_typed_map_rows(value["releaseBindings"], _sps_typed_id, _sps_typed_digest)
        # Rev4.1 has no accepted grammar for adaptive persistent invariants.
        and value["persistentInvariants"] == []
        and _sps_typed_tag(value["invocationClaim"], "SingleInvocation")
        and _sps_typed_map_rows(value["contractBindings"], _sps_typed_id, _sps_typed_id)
    )


def _sps_typed_abi_root(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["rootId", "argumentIndex", "fixedByteLength", "alignmentBytes", "permission", "entryInitialization", "host", "lifetimeOwner"]
        and _sps_typed_id(value["rootId"]) and _sps_typed_nat(value["argumentIndex"])
        and _sps_typed_nat(value["fixedByteLength"]) and _sps_typed_pos(value["alignmentBytes"])
        and value["alignmentBytes"] & (value["alignmentBytes"] - 1) == 0
        and value["permission"] in {"ReadOnly", "WriteOnly", "ReadWrite"}
        and value["entryInitialization"] in {"Initialized", "Uninitialized"}
        and _sps_typed_id(value["host"]) and value["lifetimeOwner"] in {"Caller", "Entry"}
    )


def _sps_typed_payload_reference(value: Any) -> bool:
    return any(_sps_typed_args(value, tag, [_sps_typed_id]) for tag in [
        "ContractMetadataOutputPayloadV2", "ContractFailureOutputPayloadV2",
    ])


def _sps_typed_output_source(value: Any) -> bool:
    return any([
        _sps_typed_args(value, "ReturnBitsV2", [_sps_typed_id, _sps_typed_nat, _sps_typed_pos, _sps_typed_bit_encoding]),
        _sps_typed_args(value, "RootBytesAtTerminationV2", [_sps_typed_id, _sps_typed_id, _sps_typed_nat, _sps_typed_pos, _sps_typed_bit_encoding]),
        _sps_typed_args(value, "ContractEventBytesV2", [_sps_typed_id, _sps_typed_nat, _sps_typed_payload_reference, _sps_typed_pos, _sps_typed_bit_encoding]),
    ])


def _sps_typed_output_footprint(value: Any) -> bool:
    return any([
        _sps_typed_args(value, "ReturnBitV2", [_sps_typed_id, _sps_typed_nat]),
        _sps_typed_args(value, "RootByteV2", [_sps_typed_id, _sps_typed_id, _sps_typed_nat]),
        _sps_typed_args(value, "ContractEventByteV2", [_sps_typed_id, _sps_typed_nat, _sps_typed_payload_reference, _sps_typed_nat]),
    ])


def _sps_typed_error_source(value: Any) -> bool:
    return any([
        _sps_typed_args(value, "ReturnBitsAtFailureV2", [_sps_typed_id, _sps_typed_return_class, _sps_typed_nat, _sps_typed_pos, _sps_typed_bit_encoding]),
        _sps_typed_args(value, "RootSliceAtFailureV2", [_sps_typed_id, _sps_typed_return_class, _sps_typed_root_slice]),
        _sps_typed_args(value, "ContractFailureErrorSourceV2", [_sps_typed_id, _sps_typed_id]),
        _sps_typed_tag(value, "VerifierUBRiskPayloadV2"),
    ])


def _sps_abi_payload_is_typed(value: Any) -> bool:
    def entry(entry_value: Any) -> bool:
        return (
            isinstance(entry_value, dict)
            and list(entry_value) == ["functionType", "roots", "returnObservationHost", "returnBitWidth", "declaredErrorFields"]
            and isinstance(entry_value["functionType"], str)
            and isinstance(entry_value["roots"], list) and _sps_typed_unique_list(entry_value["roots"])
            and all(_sps_typed_abi_root(item) for item in entry_value["roots"])
            and _sps_typed_id(entry_value["returnObservationHost"])
            and _sps_typed_map_rows(entry_value["returnBitWidth"], _sps_typed_return_class, _sps_typed_nat)
            and _sps_typed_id_list(entry_value["declaredErrorFields"])
        )

    def named_carrier(item: Any) -> bool:
        return _sps_typed_args(item, "ValueCarrierDeclV2", [_sps_typed_manifest_value_type, _sps_typed_carrier])

    def output_binding(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["outputId", "source", "footprint"]
            and _sps_typed_id(item["outputId"]) and _sps_typed_output_source(item["source"])
            and isinstance(item["footprint"], list) and bool(item["footprint"])
            and _sps_typed_unique_list(item["footprint"], nonempty=True)
            and all(_sps_typed_output_footprint(part) for part in item["footprint"])
        )

    def error_binding(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["errorFieldId", "payloadType", "source", "encoding"]
            and _sps_typed_id(item["errorFieldId"]) and _sps_typed_manifest_value_type(item["payloadType"])
            and _sps_typed_error_source(item["source"]) and _sps_typed_bit_encoding(item["encoding"])
        )

    def alias_topology(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["equivalenceClasses", "overlaps"]
            and isinstance(item["equivalenceClasses"], list)
            and all(_sps_typed_id_list(group, nonempty=True) for group in item["equivalenceClasses"])
            and item["overlaps"] == []
        )

    pair_ids = lambda item: isinstance(item, list) and len(item) == 2 and all(_sps_typed_id(part) for part in item)
    entry_return = lambda item: isinstance(item, list) and len(item) == 2 and _sps_typed_id(item[0]) and _sps_typed_return_class(item[1])
    boundary_ordinal = lambda item: isinstance(item, list) and len(item) == 2 and _sps_typed_id(item[0]) and _sps_typed_nat(item[1])
    return (
        _sps_typed_digest(value["abiId"]) and isinstance(value["targetDataLayout"], str)
        and _sps_typed_map_rows(value["entries"], _sps_typed_id, entry)
        and _sps_typed_map_rows(value["carriers"], pair_ids, _sps_typed_carrier)
        and _sps_typed_map_rows(value["namedCarriers"], _sps_typed_id, named_carrier)
        and _sps_typed_map_rows(value["outputBindings"], _sps_typed_id, output_binding)
        and _sps_typed_map_rows(value["returnClassBindings"], pair_ids, _sps_typed_return_class)
        and _sps_typed_map_rows(value["terminalOutputOrder"], entry_return, _sps_typed_id_list)
        and _sps_typed_map_rows(value["contractEventOutputOrder"], boundary_ordinal, _sps_typed_id_list)
        and _sps_typed_map_rows(value["errorFields"], _sps_typed_id, error_binding)
        and _sps_typed_id(value["ubRiskErrorFieldId"])
        and _sps_typed_map_rows(value["aliasTopologyBindings"], pair_ids, alias_topology)
    )


def _sps_typed_relation_field_type(value: Any) -> bool:
    return any([
        _sps_typed_tag(value, "BoolFieldV2"),
        _sps_typed_args(value, "BVFieldV2", [_sps_typed_pos]),
        _sps_typed_args(value, "NatFieldV2", [_sps_typed_nat]),
        _sps_typed_args(value, "FiniteTagFieldV2", [_sps_typed_id, lambda items: _sps_typed_id_list(items, nonempty=True)]),
    ])


def _sps_typed_relation_tuple_type(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["fields"]
        and isinstance(value["fields"], list) and bool(value["fields"])
        and _sps_typed_unique_list(value["fields"], nonempty=True)
        and all(
            isinstance(field, dict) and list(field) == ["fieldPath", "fieldType"]
            and _sps_typed_relation_field_path(field["fieldPath"])
            and _sps_typed_relation_field_type(field["fieldType"])
            for field in value["fields"]
        )
    )


def _sps_typed_relation_field_value(value: Any) -> bool:
    return any([
        _sps_typed_args(value, "BoolFieldValueV2", [lambda item: isinstance(item, bool)]),
        _sps_typed_args(value, "BVFieldValueV2", [_sps_typed_pos, lambda item: isinstance(item, str) and re.fullmatch(r"[01]+", item) is not None]),
        _sps_typed_args(value, "NatFieldValueV2", [_sps_typed_nat, _sps_typed_nat]),
        _sps_typed_args(value, "FiniteTagFieldValueV2", [_sps_typed_id, _sps_typed_id]),
    ])


def _sps_typed_relation_tuple_value(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["fields"]
        and isinstance(value["fields"], list)
        and all(_sps_typed_relation_field_value(item) for item in value["fields"])
    )


def _sps_typed_finite_pair_table(value: Any) -> bool:
    if (
        not isinstance(value, dict)
        or list(value) != ["leftValues", "rightValues", "allowedPairBitmap"]
        or not isinstance(value["leftValues"], list)
        or not isinstance(value["rightValues"], list)
        or not _sps_typed_canonical_unique_list(value["leftValues"])
        or not _sps_typed_canonical_unique_list(value["rightValues"])
        or not all(_sps_typed_relation_tuple_value(item) for item in value["leftValues"] + value["rightValues"])
        or not isinstance(value["allowedPairBitmap"], str)
        or re.fullmatch(r"[01]*", value["allowedPairBitmap"]) is None
    ):
        return False
    return len(value["allowedPairBitmap"]) == len(value["leftValues"]) * len(value["rightValues"])


def _sps_typed_canonical_relation(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["relationId", "relationRole", "leftTupleType", "rightTupleType", "representation"]
        and _sps_typed_id(value["relationId"])
        and any(_sps_typed_tag(value["relationRole"], tag) for tag in ["MechanismPairedCoupling", "TimingPairedCoupling"])
        and _sps_typed_relation_tuple_type(value["leftTupleType"])
        and _sps_typed_relation_tuple_type(value["rightTupleType"])
        and (_sps_typed_policy_expr(value["representation"]) or _sps_typed_finite_pair_table(value["representation"]))
    )


def _sps_typed_contract_value_type(value: Any) -> bool:
    return (
        _sps_typed_args(value, "ValueV2", [lambda item:
            _sps_typed_tag(item, "BoolValueV2") or _sps_typed_args(item, "BVValueV2", [_sps_typed_pos])])
        or _sps_typed_args(value, "ExistingPointerV2", [lambda item: item == 0])
    )


def _sps_typed_contract_field_decl(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["fieldId", "valueType"]
        and _sps_typed_id(value["fieldId"]) and _sps_typed_contract_value_type(value["valueType"])
    )


def _sps_typed_contract_function(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["functionId", "inputTupleType", "outputTupleType", "outputExpressions"]
        and _sps_typed_id(value["functionId"])
        and _sps_typed_relation_tuple_type(value["inputTupleType"])
        and _sps_typed_relation_tuple_type(value["outputTupleType"])
        and isinstance(value["outputExpressions"], list) and bool(value["outputExpressions"])
        and _sps_typed_unique_list(value["outputExpressions"], nonempty=True)
        and all(
            isinstance(row, dict) and list(row) == ["fieldPath", "expression"]
            and _sps_typed_relation_field_path(row["fieldPath"])
            and _sps_typed_policy_expr(row["expression"])
            for row in value["outputExpressions"]
        )
    )


def _sps_typed_contract_event_slot(value: Any) -> bool:
    return any(_sps_typed_args(value, tag, [_sps_typed_id]) for tag in ["MetadataSlotV2", "FailureSlotV2"])


def _sps_contract_payload_is_typed(value: Any) -> bool:
    def signature(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["arguments", "result"]
            and isinstance(item["arguments"], list)
            and _sps_typed_unique_list(item["arguments"])
            and all(_sps_typed_contract_field_decl(field) for field in item["arguments"])
            and _sps_typed_option(item["result"], _sps_typed_contract_field_decl)
        )

    def occurrence(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["boundaryId", "site", "choiceType", "eventOrder"]
            and _sps_typed_id(item["boundaryId"]) and _sps_typed_id(item["site"])
            and _sps_typed_tag(item["choiceType"], "Unit")
            and isinstance(item["eventOrder"], list)
            and _sps_typed_unique_list(item["eventOrder"])
            and all(_sps_typed_contract_event_slot(slot) for slot in item["eventOrder"])
        )

    def object_slice(item: Any) -> bool:
        return (
            _sps_typed_args(item, "PointerArgumentSliceV2", [_sps_typed_nat, _sps_typed_nat, _sps_typed_pos])
            or _sps_typed_args(item, "GlobalSliceV2", [_sps_typed_id, _sps_typed_nat, _sps_typed_pos])
        )

    def memory_effect(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["effectId", "kind", "target"]
            and _sps_typed_id(item["effectId"]) and item["kind"] in {"Read", "Write", "Initialize"}
            and object_slice(item["target"])
        )

    def failure(item: Any) -> bool:
        return (
            isinstance(item, dict)
            and list(item) == ["failureId", "errorFieldId", "payloadType", "eventOrdinal", "location"]
            and _sps_typed_id(item["failureId"]) and _sps_typed_id(item["errorFieldId"])
            and _sps_typed_manifest_value_type(item["payloadType"])
            and _sps_typed_nat(item["eventOrdinal"])
            and item["location"] in {"BoundarySource", "BoundaryDestinations"}
        )

    def metadata(item: Any) -> bool:
        return (
            isinstance(item, dict)
            and list(item) == ["metadataFieldId", "valueType", "eventOrdinal", "location"]
            and _sps_typed_id(item["metadataFieldId"])
            and _sps_typed_manifest_value_type(item["valueType"])
            and _sps_typed_nat(item["eventOrdinal"])
            and item["location"] in {"BoundarySource", "BoundaryDestinations"}
        )

    def contract(item: Any) -> bool:
        expected = [
            "contractId", "supportedCoalitionMaxima", "signature", "stateType",
            "choiceDomain", "occurrences", "function", "pairedChoiceCoupling",
            "memoryEffects", "failures", "contractVisibleMetadata",
            "contractMetadataVisibility", "stateRelation", "releaseBehavior",
            "freshAllocationBehavior", "versionAndImplementationBoundary",
        ]
        return (
            isinstance(item, dict) and list(item) == expected
            and _sps_typed_id(item["contractId"])
            and isinstance(item["supportedCoalitionMaxima"], list)
            and _sps_typed_canonical_unique_list(item["supportedCoalitionMaxima"], nonempty=True)
            and all(_sps_typed_id_list(coalition) for coalition in item["supportedCoalitionMaxima"])
            and signature(item["signature"])
            and _sps_typed_tag(item["stateType"], "None")
            and item["choiceDomain"] == [OrderedDict([("tag", "Unit")])]
            and _sps_typed_map_rows(item["occurrences"], _sps_typed_id, occurrence)
            and _sps_typed_contract_function(item["function"])
            and _sps_typed_map_rows(item["pairedChoiceCoupling"], _sps_typed_digest, _sps_typed_canonical_relation)
            and isinstance(item["memoryEffects"], list) and all(memory_effect(effect) for effect in item["memoryEffects"])
            and _sps_typed_unique_list(item["memoryEffects"])
            and isinstance(item["failures"], list) and _sps_typed_unique_list(item["failures"])
            and all(failure(row) for row in item["failures"])
            and _sps_typed_map_rows(item["contractVisibleMetadata"], _sps_typed_id, metadata)
            and _sps_typed_visibility(item["contractMetadataVisibility"])
            and _sps_typed_tag(item["stateRelation"], "None")
            and _sps_typed_tag(item["releaseBehavior"], "NoContractReleaseV2")
            and _sps_typed_tag(item["freshAllocationBehavior"], "NoFreshContractAllocationV2")
            and _sps_typed_digest(item["versionAndImplementationBoundary"])
        )

    return (
        value["formatId"] == "SPS-ContractTable-v2"
        and isinstance(value["contracts"], list)
        and all(contract(item) for item in value["contracts"])
        and [item["contractId"] for item in value["contracts"]]
        == sorted(item["contractId"] for item in value["contracts"])
        and len({item["contractId"] for item in value["contracts"]}) == len(value["contracts"])
    )


def _sps_typed_release_type(value: Any) -> bool:
    if _sps_typed_args(value, "BVType", [_sps_typed_pos, lambda item: item in {"LittleEndian", "BigEndian"}]):
        return True
    return _sps_typed_args(value, "TupleType", [
        lambda fields: isinstance(fields, list) and bool(fields)
        and all(
            isinstance(field, list) and len(field) == 2 and _sps_typed_id(field[0])
            and _sps_typed_release_type(field[1])
            for field in fields
        )
        and len({field[0] for field in fields}) == len(fields)
    ])


def _sps_typed_release_spec(value: Any, expression_semantics: Any) -> bool:
    fields = [
        "releaseId", "site", "implementation", "type", "expression",
        "occurrenceGuard", "audience", "footprint", "multiplicity",
        "activationClaims", "deterministicSemantics",
    ]
    if not isinstance(value, dict) or list(value) != fields:
        return False
    implementation = value["implementation"]
    audience = value["audience"]
    return (
        _sps_typed_id(value["releaseId"]) and _sps_typed_id(value["site"])
        and isinstance(implementation, dict)
        and list(implementation) == ["wrapperFunction", "emitMarkerInstructionId"]
        and _sps_typed_id(implementation["wrapperFunction"])
        and _sps_typed_id(implementation["emitMarkerInstructionId"])
        and _sps_typed_release_type(value["type"])
        and _sps_typed_policy_expr(value["expression"])
        and _sps_typed_policy_expr(value["occurrenceGuard"])
        and isinstance(audience, dict)
        and list(audience) == ["worldVisible", "memberVisible", "minimallyJointVisible"]
        and isinstance(audience["worldVisible"], bool)
        and _sps_typed_id_list(audience["memberVisible"])
        and isinstance(audience["minimallyJointVisible"], list)
        and _sps_typed_canonical_unique_list(audience["minimallyJointVisible"])
        and all(_sps_typed_id_list(coalition, nonempty=True) for coalition in audience["minimallyJointVisible"])
        and isinstance(value["footprint"], list) and bool(value["footprint"])
        and _sps_typed_canonical_unique_list(value["footprint"], nonempty=True)
        and all(_sps_typed_args(item, "ReleasePayloadByteV2", [_sps_typed_nat]) for item in value["footprint"])
        and _sps_typed_policy_expr(value["multiplicity"])
        and _sps_typed_map_rows(value["activationClaims"], _sps_typed_id, lambda item:
            _sps_typed_tag(item, "RequiredReachable") or _sps_typed_tag(item, "NotApplicable")
            or (isinstance(item, dict) and list(item) == ["tag", "reasonCode"]
                and item["tag"] == "Dormant" and _sps_typed_id(item["reasonCode"])))
        and value["deterministicSemantics"] == expression_semantics
    )


def _sps_typed_option_row(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["name", "value"]
        and isinstance(value["name"], str)
        and (
            isinstance(value["value"], (bool, str))
            or _sps_typed_nat(value["value"])
        )
    )


def _sps_typed_alias_topology(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["equivalenceClasses", "overlaps"]
        and isinstance(value["equivalenceClasses"], list)
        and _sps_typed_canonical_unique_list(value["equivalenceClasses"])
        and all(_sps_typed_id_list(group, nonempty=True) for group in value["equivalenceClasses"])
        and value["overlaps"] == []
    )


def _sps_typed_manifest_value(value: Any) -> bool:
    if _sps_typed_args(value, "BoolLiteralValueV2", [lambda item: isinstance(item, bool)]):
        return True
    if _sps_typed_args(value, "BVLiteralValueV2", [
        _sps_typed_pos,
        lambda item: isinstance(item, str) and re.fullmatch(r"[01]+", item) is not None,
    ]):
        return len(value["args"][1]) == value["args"][0]
    if _sps_typed_args(value, "FixedBytesLiteralValueV2", [
        _sps_typed_pos,
        lambda item: isinstance(item, str) and re.fullmatch(r"(?:[0-9a-f]{2})+", item) is not None,
    ]):
        return len(value["args"][1]) == 2 * value["args"][0]
    return _sps_typed_args(value, "TupleLiteralValueV2", [
        lambda items: isinstance(items, list) and bool(items)
        and all(_sps_typed_manifest_value(item) for item in items)
    ])


def _sps_typed_public_configuration_source(value: Any) -> bool:
    return any([
        _sps_typed_args(value, "ComponentConfigV2", [_sps_typed_id]),
        _sps_typed_args(value, "BoundConfigV2", [_sps_typed_id]),
        _sps_typed_args(value, "ReleaseOccurrenceCounterConfigV2", [_sps_typed_id, _sps_typed_nat_sort]),
        _sps_typed_args(value, "TimingOccurrenceCounterConfigV2", [_sps_typed_id, _sps_typed_nat_sort]),
    ])


def _sps_typed_public_configuration_value(value: Any) -> bool:
    return (
        _sps_typed_args(value, "ComponentConfigValueV2", [_sps_typed_manifest_value])
        or _sps_typed_args(value, "NaturalConfigValueV2", [_sps_typed_nat_sort, _sps_typed_nat])
    )


def _sps_llvm_build_payload_is_typed(value: Any) -> bool:
    return (
        isinstance(value["repository"], str) and isinstance(value["tag"], str)
        and isinstance(value["commit"], str) and re.fullmatch(r"[0-9a-f]{40}", value["commit"]) is not None
        and _sps_typed_digest(value["compilerBinaryDigest"])
        and isinstance(value["libraryDigests"], list)
        and _sps_typed_canonical_unique_list(value["libraryDigests"])
        and all(
            isinstance(row, dict) and list(row) == ["name", "digest"]
            and isinstance(row["name"], str) and _sps_typed_digest(row["digest"])
            for row in value["libraryDigests"]
        )
        and len({row["name"] for row in value["libraryDigests"]}) == len(value["libraryDigests"])
    )


def _sps_sps_build_payload_is_typed(value: Any) -> bool:
    return (
        isinstance(value["patchCommit"], str) and re.fullmatch(r"[0-9a-f]{40}", value["patchCommit"]) is not None
        and all(_sps_typed_digest(value[field]) for field in [
            "verifierCoreBinaryDigest", "normalizerBinaryDigest", "auditorBinaryDigest",
            "transitionRuleTableDigest",
        ])
        and _sps_typed_id(value["normalizerId"]) and _sps_typed_id(value["auditorId"])
        and isinstance(value["normalizerOptions"], list)
        and all(_sps_typed_option_row(row) for row in value["normalizerOptions"])
    )


def _sps_pass_trace_payload_is_typed(value: Any) -> bool:
    freeze = value["freezeCoordinate"]
    return (
        isinstance(value["rows"], list) and bool(value["rows"])
        and all(
            isinstance(row, dict)
            and list(row) == ["ordinal", "passId", "implementationDigest", "pluginDigest", "options", "mutatesIR"]
            and _sps_typed_nat(row["ordinal"]) and _sps_typed_id(row["passId"])
            and _sps_typed_digest(row["implementationDigest"])
            and _sps_typed_option(row["pluginDigest"], _sps_typed_digest)
            and isinstance(row["options"], list) and all(_sps_typed_option_row(item) for item in row["options"])
            and isinstance(row["mutatesIR"], bool)
            for row in value["rows"]
        )
        and [row["ordinal"] for row in value["rows"]] == list(range(len(value["rows"])))
        and isinstance(freeze, dict)
        and list(freeze) == ["llvmCommit", "targetPassConfigConcreteClass", "instructionSelector"]
        and isinstance(freeze["llvmCommit"], str) and re.fullmatch(r"[0-9a-f]{40}", freeze["llvmCommit"]) is not None
        and all(isinstance(freeze[field], str) for field in ["targetPassConfigConcreteClass", "instructionSelector"])
    )


def _sps_target_configuration_payload_is_typed(value: Any) -> bool:
    string_fields = [
        "targetTriple", "dataLayout", "targetCPU", "tuneCPU", "relocationModel",
        "codeModel", "codegenOptimizationLevel", "floatABI", "instructionSelector",
        "ltoMode", "sanitizerMode",
    ]
    return (
        all(isinstance(value[field], str) for field in string_fields)
        and isinstance(value["targetFeatures"], list)
        and _sps_typed_canonical_unique_list(value["targetFeatures"])
        and all(isinstance(item, str) for item in value["targetFeatures"])
        and all(isinstance(value[field], bool) for field in [
            "fastISelEnabled", "globalISelEnabled", "globalISelFallbackEnabled",
        ])
        and isinstance(value["canonicalBitcodeWriterOptions"], list)
        and all(_sps_typed_option_row(row) for row in value["canonicalBitcodeWriterOptions"])
    )


def _sps_placement_payload_is_typed(value: Any) -> bool:
    def location(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["source", "destinations"]
            and _sps_typed_id(item["source"]) and _sps_typed_id_list(item["destinations"])
        )

    return (
        value["formatId"] == "SPS-FunctionPlacement-v2"
        and all(_sps_typed_map_rows(value[field], _sps_typed_id, _sps_typed_id) for field in [
            "functionHost", "instructionHost", "globalHost",
        ])
        and _sps_typed_map_rows(value["boundaryLocations"], _sps_typed_id, location)
    )


def _sps_alias_topology_payload_is_typed(value: Any) -> bool:
    pair_ids = lambda item: isinstance(item, list) and len(item) == 2 and all(_sps_typed_id(part) for part in item)
    return (
        value["formatId"] == "SPS-Alias-Topology-Digest-Preimage-v2"
        and _sps_typed_id_list(value["selectedTopologyIds"])
        and _sps_typed_map_rows(value["bindings"], pair_ids, _sps_typed_alias_topology)
    )


def _sps_stable_ir_payload_is_typed(value: Any) -> bool:
    def exact_record(item: Any, names: list[str], predicates: list[Any]) -> bool:
        return (
            isinstance(item, dict) and list(item) == names
            and all(predicate(item[name]) for name, predicate in zip(names, predicates))
        )

    synthetic_roles = {
        "ReleaseBoundary", "BoundRemainder", "ReleaseGuard", "ReleaseValue",
        "OutputBoundary", "ContractBoundary", "FailureBoundary",
    }
    synthetic = lambda item: (
        _sps_typed_args(item, "InstructionSyntheticSiteLocatorV2", [_sps_typed_id, lambda role: role in synthetic_roles, _sps_typed_nat])
        or _sps_typed_args(item, "LoopSyntheticSiteLocatorV2", [_sps_typed_id, lambda role: role == "BoundRemainder", lambda ordinal: ordinal == 0])
    )
    validators = {
        "functions": lambda item: exact_record(item, ["functionSymbol"], [lambda field: isinstance(field, str)]),
        "blocks": lambda item: exact_record(item, ["functionId", "blockOrdinal"], [_sps_typed_id, _sps_typed_nat]),
        "arguments": lambda item: exact_record(item, ["functionId", "argumentOrdinal"], [_sps_typed_id, _sps_typed_nat]),
        "instructions": lambda item: exact_record(item, ["functionId", "blockOrdinal", "instructionOrdinal"], [_sps_typed_id, _sps_typed_nat, _sps_typed_nat]),
        "predecessorEdges": lambda item: exact_record(item, ["functionId", "predecessorBlockOrdinal", "successorBlockOrdinal", "successorOperandOrdinal"], [_sps_typed_id, _sps_typed_nat, _sps_typed_nat, _sps_typed_nat]),
        "loops": lambda item: exact_record(item, ["functionId", "headerBlockOrdinal", "orderedBackedgeIds"], [_sps_typed_id, _sps_typed_nat, _sps_typed_id_list]),
        "instructionSites": lambda item: exact_record(item, ["ownerInstructionId", "siteRole", "roleOrdinal"], [_sps_typed_id, lambda role: role == "OrdinaryTransition", lambda ordinal: ordinal == 0]),
        "syntheticSites": synthetic,
    }
    if not all(
        isinstance(value[field], list) and all(predicate(item) for item in value[field])
        for field, predicate in validators.items()
    ) or not all(_sps_typed_unique_list(value[field]) for field in validators):
        return False
    order_keys = {
        "functions": lambda row: (row["functionSymbol"],),
        "blocks": lambda row: (row["functionId"], row["blockOrdinal"]),
        "arguments": lambda row: (row["functionId"], row["argumentOrdinal"]),
        "instructions": lambda row: (row["functionId"], row["blockOrdinal"], row["instructionOrdinal"]),
        "predecessorEdges": lambda row: (row["functionId"], row["predecessorBlockOrdinal"], row["successorBlockOrdinal"], row["successorOperandOrdinal"]),
        "loops": lambda row: (row["functionId"], row["headerBlockOrdinal"]),
        "instructionSites": lambda row: (row["ownerInstructionId"], row["siteRole"], row["roleOrdinal"]),
        "syntheticSites": lambda row: (row["tag"], *row["args"]),
    }
    return all(
        value[field] == sorted(value[field], key=key)
        for field, key in order_keys.items()
    )


def _sps_timing_environment_payload_is_typed(value: Any) -> bool:
    def occurrence(item: Any) -> bool:
        return (
            isinstance(item, dict)
            and list(item) == ["timingOccurrenceId", "site", "occurrenceGuard", "multiplicity", "configurationSources", "allowedChoiceIds"]
            and _sps_typed_id(item["timingOccurrenceId"]) and _sps_typed_id(item["site"])
            and _sps_typed_policy_expr(item["occurrenceGuard"])
            and _sps_typed_policy_expr(item["multiplicity"])
            and isinstance(item["configurationSources"], list)
            and _sps_typed_canonical_unique_list(item["configurationSources"])
            and all(_sps_typed_public_configuration_source(source) for source in item["configurationSources"])
            and _sps_typed_id_list(item["allowedChoiceIds"], nonempty=True)
        )

    def latency_row(item: Any) -> bool:
        return (
            isinstance(item, dict)
            and list(item) == ["timingOccurrenceId", "publicConfigurationValues", "choiceId", "latencyClassId"]
            and _sps_typed_id(item["timingOccurrenceId"])
            and isinstance(item["publicConfigurationValues"], list)
            and all(_sps_typed_public_configuration_value(part) for part in item["publicConfigurationValues"])
            and _sps_typed_id(item["choiceId"]) and _sps_typed_id(item["latencyClassId"])
        )

    return (
        _sps_typed_digest(value["timingEnvironmentId"])
        and isinstance(value["choiceDomain"], list)
        and _sps_typed_canonical_unique_list(value["choiceDomain"])
        and all(isinstance(row, dict) and list(row) == ["choiceId"] and _sps_typed_id(row["choiceId"]) for row in value["choiceDomain"])
        and _sps_typed_map_rows(value["occurrences"], _sps_typed_id, occurrence)
        and isinstance(value["latencyMeaning"], list)
        and _sps_typed_canonical_unique_list(value["latencyMeaning"])
        and all(latency_row(row) for row in value["latencyMeaning"])
        and isinstance(value["latencyClasses"], list) and bool(value["latencyClasses"])
        and _sps_typed_canonical_unique_list(value["latencyClasses"], nonempty=True)
        and all(isinstance(row, dict) and list(row) == ["latencyClassId"] and _sps_typed_id(row["latencyClassId"]) for row in value["latencyClasses"])
        and _sps_typed_map_rows(value["pairedChoiceCoupling"], _sps_typed_digest, _sps_typed_canonical_relation)
        and _sps_typed_digest(value["versionAndObservationBoundary"])
    )


def _sps_latency_class_payload_is_typed(value: Any) -> bool:
    return (
        isinstance(value["siteSchemas"], list)
        and _sps_typed_canonical_unique_list(value["siteSchemas"])
        and all(
            isinstance(row, dict) and list(row) == ["siteId", "configurationSources", "timingOccurrenceId"]
            and _sps_typed_id(row["siteId"]) and isinstance(row["configurationSources"], list)
            and _sps_typed_canonical_unique_list(row["configurationSources"])
            and all(_sps_typed_public_configuration_source(item) for item in row["configurationSources"])
            and _sps_typed_option(row["timingOccurrenceId"], _sps_typed_id)
            for row in value["siteSchemas"]
        )
        and isinstance(value["rows"], list)
        and _sps_typed_canonical_unique_list(value["rows"])
        and all(
            isinstance(row, dict) and list(row) == ["siteId", "publicConfigurationValues", "timingChoiceId", "latencyClassId"]
            and _sps_typed_id(row["siteId"]) and isinstance(row["publicConfigurationValues"], list)
            and all(_sps_typed_public_configuration_value(item) for item in row["publicConfigurationValues"])
            and _sps_typed_option(row["timingChoiceId"], _sps_typed_id) and _sps_typed_id(row["latencyClassId"])
            for row in value["rows"]
        )
    )


def _sps_entry_scope_payload_is_typed(value: Any) -> bool:
    return (
        isinstance(value["rows"], list) and bool(value["rows"])
        and all(
            isinstance(row, dict)
            and list(row) == ["entryId", "entryFunctionId", "reachableFunctionIds", "reachableBoundaryIds", "reachableReleaseIds"]
            and _sps_typed_id(row["entryId"]) and _sps_typed_id(row["entryFunctionId"])
            and all(_sps_typed_id_list(row[field]) for field in ["reachableFunctionIds", "reachableBoundaryIds", "reachableReleaseIds"])
            for row in value["rows"]
        )
        and [row["entryId"] for row in value["rows"]] == sorted(row["entryId"] for row in value["rows"])
        and len({row["entryId"] for row in value["rows"]}) == len(value["rows"])
    )


def _sps_profile_configuration_payload_is_typed(value: Any) -> bool:
    return (
        all(_sps_typed_digest(value[field]) for field in [
            "globalRegionTableDigest", "preflightTaskScheduleDigest", "publicAliasTopologyDigest",
        ])
        and isinstance(value["integerWidths"], list) and bool(value["integerWidths"])
        and all(_sps_typed_pos(item) for item in value["integerWidths"])
        and value["integerWidths"] == sorted(value["integerWidths"])
        and len(set(value["integerWidths"])) == len(value["integerWidths"])
        and isinstance(value["floatTypes"], list) and all(isinstance(item, str) for item in value["floatTypes"])
        and _sps_typed_pos(value["maxVectorLanesBeforeNormalization"])
        and isinstance(value["loopBoundBindings"], list)
        and _sps_typed_canonical_unique_list(value["loopBoundBindings"])
        and all(
            isinstance(row, dict) and list(row) == ["loopId", "boundId", "engineCap"]
            and _sps_typed_id(row["loopId"]) and _sps_typed_id(row["boundId"]) and _sps_typed_nat(row["engineCap"])
            for row in value["loopBoundBindings"]
        )
        and isinstance(value["allocaSizeBindings"], list)
        and _sps_typed_canonical_unique_list(value["allocaSizeBindings"])
        and all(
            isinstance(row, dict) and list(row) == ["allocaSiteId", "expressionSiteId"]
            and _sps_typed_id(row["allocaSiteId"]) and _sps_typed_id(row["expressionSiteId"])
            for row in value["allocaSizeBindings"]
        )
        and _sps_typed_pos(value["enginePathCap"]) and _sps_typed_pos(value["engineByteCap"])
        and all(isinstance(value[field], str) for field in [
            "moduleFlagPolicy", "codegenAttributePolicy", "stackProtectorPolicy",
        ])
    )


def _sps_global_region_payload_is_typed(value: Any) -> bool:
    def row_is_typed(row: Any) -> bool:
        expected = [
            "globalId", "llvmSymbol", "llvmStorageType", "linkage", "mutability",
            "storageEncoding", "sizeBytes", "alignmentBytes", "addressSpace",
            "initializerBytes", "host", "applicableEntries",
        ]
        return (
            isinstance(row, dict) and list(row) == expected
            and _sps_typed_id(row["globalId"]) and isinstance(row["llvmSymbol"], str)
            and isinstance(row["llvmStorageType"], str) and row["linkage"] in {"Internal", "Private"}
            and row["mutability"] == "ImmutableV2"
            and row["storageEncoding"] == "PointerFreePaddingFreeExactBytesV2"
            and _sps_typed_nat(row["sizeBytes"]) and _sps_typed_pos(row["alignmentBytes"])
            and row["alignmentBytes"] & (row["alignmentBytes"] - 1) == 0
            and row["addressSpace"] == 0 and isinstance(row["initializerBytes"], str)
            and re.fullmatch(r"[0-9a-f]*", row["initializerBytes"]) is not None
            and len(row["initializerBytes"]) == 2 * row["sizeBytes"]
            and _sps_typed_id(row["host"]) and _sps_typed_id_list(row["applicableEntries"], nonempty=True)
        )

    return (
        isinstance(value["rows"], list) and all(row_is_typed(row) for row in value["rows"])
        and [row["globalId"] for row in value["rows"]] == sorted(row["globalId"] for row in value["rows"])
        and len({row["globalId"] for row in value["rows"]}) == len(value["rows"])
    )


def _sps_preflight_schedule_payload_is_typed(value: Any) -> bool:
    return (
        value["formatId"] == "SPS-Preflight-Task-Schedule-v2"
        and isinstance(value["tasks"], list)
        and all(
            isinstance(row, dict)
            and list(row) == ["taskId", "entryScope", "scannerId", "scannerImplementationDigest", "taskClass"]
            and _sps_typed_id(row["taskId"]) and _sps_typed_option(row["entryScope"], _sps_typed_id)
            and _sps_typed_id(row["scannerId"]) and _sps_typed_digest(row["scannerImplementationDigest"])
            and _sps_typed_id(row["taskClass"])
            for row in value["tasks"]
        )
        and [row["taskId"] for row in value["tasks"]] == sorted(row["taskId"] for row in value["tasks"])
        and len({row["taskId"] for row in value["tasks"]}) == len(value["tasks"])
    )


def _sps_payload_shape_matches(value: Any, template: Any, field_name: str | None = None) -> bool:
    if isinstance(template, dict):
        if not isinstance(value, dict) or list(value) != list(template):
            return False
        for key in template:
            if not _sps_payload_shape_matches(value[key], template[key], key):
                return False
        return True
    if isinstance(template, list):
        if not isinstance(value, list):
            return False
        if not template:
            return True
        if len(template) == 1:
            return all(_sps_payload_shape_matches(item, template[0]) for item in value)
        return len(value) == len(template) and all(
            _sps_payload_shape_matches(item, expected)
            for item, expected in zip(value, template)
        )
    if isinstance(template, bool):
        return isinstance(value, bool)
    if isinstance(template, int):
        return not isinstance(value, bool) and isinstance(value, int) and value >= 0
    if isinstance(template, str):
        if not isinstance(value, str):
            return False
        if field_name is not None and field_name.lower().endswith("digest"):
            return HEX_RE.fullmatch(value) is not None
        return True
    return type(value) is type(template)


class Registry:
    def __init__(self, value: Any, distribution: Path | None = None):
        if not isinstance(value, dict):
            raise InterfaceError("interface registry must be an object")
        for key in (
            "schemaSetId",
            "records",
            "unions",
            "enums",
            "formatLiterals",
            "rootSchemaIds",
            "semanticRules",
        ):
            if key not in value:
                raise InterfaceError(f"interface registry is missing {key}")
        self.value = value
        self.records: dict[str, Any] = value["records"]
        self.unions: dict[str, Any] = value["unions"]
        self.enums: dict[str, Any] = value["enums"]
        self.distribution = distribution
        self._validate_metadata()

    @classmethod
    def from_path(cls, path: Path) -> "Registry":
        return cls(require_canonical(path.read_bytes()), path.parent)

    def _validate_metadata(self) -> None:
        for name, record in self.records.items():
            fields = record.get("fields")
            order = record.get("canonicalFieldOrder")
            if not isinstance(fields, list) or not all(
                isinstance(row, dict) and set(row) == {"name", "type"}
                for row in fields
            ):
                raise InterfaceError(f"registry record {name} has malformed fields")
            names = [row["name"] for row in fields]
            if order != names or len(names) != len(set(names)):
                raise InterfaceError(f"registry record {name} has inconsistent order")
            for row in fields:
                self._validate_descriptor(row["type"], f"record {name}.{row['name']}")
        for name, union in self.unions.items():
            variants = union.get("variants")
            order = union.get("canonicalVariantOrder")
            if not isinstance(variants, list):
                raise InterfaceError(f"registry union {name} has malformed variants")
            tags = [variant.get("tag") for variant in variants]
            if order != tags or len(tags) != len(set(tags)):
                raise InterfaceError(f"registry union {name} has inconsistent order")
            for variant in variants:
                shape = variant.get("shape")
                if shape == "nullary" and set(variant) != {"tag", "shape"}:
                    raise InterfaceError(f"registry union {name} has malformed nullary arm")
                if shape == "args":
                    for desc in variant.get("args", []):
                        self._validate_descriptor(desc, f"union {name}.{variant.get('tag')}")
                elif shape == "fields":
                    for row in variant.get("fields", []):
                        self._validate_descriptor(
                            row["type"], f"union {name}.{variant.get('tag')}.{row['name']}"
                        )
                elif shape != "nullary":
                    raise InterfaceError(f"registry union {name} has unknown arm shape")

    def _validate_descriptor(self, desc: Any, where: str) -> None:
        if not isinstance(desc, dict) or not isinstance(desc.get("kind"), str):
            raise InterfaceError(f"{where}: malformed type descriptor")
        kind = desc["kind"]
        if kind == "record" and desc.get("name") not in self.records:
            raise InterfaceError(f"{where}: unknown record {desc.get('name')!r}")
        if kind == "union" and desc.get("name") not in self.unions:
            raise InterfaceError(f"{where}: unknown union {desc.get('name')!r}")
        if kind == "enum" and desc.get("name") not in self.enums:
            raise InterfaceError(f"{where}: unknown enum {desc.get('name')!r}")
        if kind in {"list", "option"}:
            self._validate_descriptor(desc.get("item"), where + " item")
        if kind == "choice":
            items = desc.get("items")
            if not isinstance(items, list) or not items:
                raise InterfaceError(f"{where}: malformed scalar choice")
            for item in items:
                self._validate_descriptor(item, where + " choice")
        if kind not in {
            "digest",
            "receipt",
            "hex",
            "id",
            "nat",
            "pos",
            "bool",
            "string",
            "opaque",
            "literal",
            "enum",
            "record",
            "union",
            "list",
            "option",
            "choice",
        }:
            raise InterfaceError(f"{where}: unknown descriptor kind {kind!r}")

    def enum_values(self, name: str) -> tuple[str, ...]:
        try:
            values = self.enums[name]["values"]
        except (KeyError, TypeError) as error:
            raise InterfaceError(f"unknown interface enum {name}") from error
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise InterfaceError(f"enum {name} has malformed values")
        return tuple(values)

    def record_fields(self, name: str) -> tuple[str, ...]:
        try:
            return tuple(self.records[name]["canonicalFieldOrder"])
        except KeyError as error:
            raise InterfaceError(f"unknown interface record {name}") from error

    def union_variants(self, name: str) -> tuple[str, ...]:
        try:
            return tuple(self.unions[name]["canonicalVariantOrder"])
        except KeyError as error:
            raise InterfaceError(f"unknown interface union {name}") from error

    def _tuple_descriptor(self, desc: dict[str, Any]) -> tuple[Any, ...]:
        kind = desc["kind"]
        if kind == "record":
            return ("rec", desc["name"])
        if kind == "union":
            return ("sum", desc["name"])
        if kind == "option":
            return ("opt", self._tuple_descriptor(desc["item"]))
        if kind == "list":
            return ("list", self._tuple_descriptor(desc["item"]))
        if kind == "choice":
            return (
                "choice",
                tuple(self._tuple_descriptor(item) for item in desc["items"]),
            )
        if kind == "literal":
            return ("lit", desc["value"])
        if kind == "enum":
            return ("enum", self.enum_values(desc["name"]))
        return ({"string": "str"}.get(kind, kind),)

    def tuple_type_tables(
        self,
    ) -> tuple[
        dict[str, tuple[tuple[str, tuple[Any, ...]], ...]],
        dict[str, dict[str, tuple[Any, ...]]],
    ]:
        records = {
            name: tuple(
                (row["name"], self._tuple_descriptor(row["type"]))
                for row in record["fields"]
            )
            for name, record in self.records.items()
        }
        unions: dict[str, dict[str, tuple[Any, ...]]] = {}
        for name, union in self.unions.items():
            variants: dict[str, tuple[Any, ...]] = {}
            for variant in union["variants"]:
                shape = variant["shape"]
                if shape == "nullary":
                    encoded: tuple[Any, ...] = ("nullary",)
                elif shape == "args":
                    encoded = (
                        "args",
                        tuple(self._tuple_descriptor(item) for item in variant["args"]),
                    )
                else:
                    encoded = (
                        "fields",
                        tuple(
                            (row["name"], self._tuple_descriptor(row["type"]))
                            for row in variant["fields"]
                        ),
                    )
                variants[variant["tag"]] = encoded
            unions[name] = variants
        return records, unions

    def validate_descriptor(self, value: Any, desc: dict[str, Any], where: str = "$") -> None:
        kind = desc["kind"]
        if kind in {"digest", "receipt"}:
            if not isinstance(value, str) or not HEX_RE.fullmatch(value):
                raise InterfaceError(f"{where}: expected 256-bit lowercase hex")
        elif kind == "hex":
            if not isinstance(value, str) or not BYTES_RE.fullmatch(value):
                raise InterfaceError(f"{where}: expected lowercase exact-byte hex")
        elif kind == "id":
            if not isinstance(value, str) or not ID_RE.fullmatch(value):
                raise InterfaceError(f"{where}: invalid stable identifier")
        elif kind == "nat":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InterfaceError(f"{where}: expected natural")
        elif kind == "pos":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise InterfaceError(f"{where}: expected positive natural")
        elif kind == "bool":
            if not isinstance(value, bool):
                raise InterfaceError(f"{where}: expected boolean")
        elif kind == "string":
            if not isinstance(value, str):
                raise InterfaceError(f"{where}: expected string")
        elif kind == "opaque":
            return
        elif kind == "literal":
            expected = desc["value"]
            if value != expected or type(value) is not type(expected):
                raise InterfaceError(f"{where}: expected literal {expected!r}")
        elif kind == "enum":
            if value not in self.enum_values(desc["name"]):
                raise InterfaceError(f"{where}: not in {desc['name']}")
        elif kind == "record":
            self.validate_record(value, desc["name"], where)
        elif kind == "union":
            self.validate_union(value, desc["name"], where)
        elif kind == "list":
            if not isinstance(value, list):
                raise InterfaceError(f"{where}: expected list")
            for index, item in enumerate(value):
                self.validate_descriptor(item, desc["item"], f"{where}[{index}]")
            if desc.get("unique"):
                encoded = [canonical_bytes(item) for item in value]
                if len(encoded) != len(set(encoded)):
                    raise InterfaceError(f"{where}: canonical unique list is duplicated")
                order = desc.get("order")
                if order in self.unions:
                    variants = self.unions[order]["variants"]
                    if any(variant["shape"] != "nullary" for variant in variants):
                        raise InterfaceError(
                            f"{where}: {order} is not a nullary ordering union"
                        )
                    expected = [{"tag": variant["tag"]} for variant in variants]
                    if value != expected:
                        raise InterfaceError(
                            f"{where}: {order} normative order mismatch"
                        )
                elif order in self.enums:
                    if value != list(self.enum_values(order)):
                        raise InterfaceError(
                            f"{where}: {order} normative order mismatch"
                        )
                elif order == "canonical-element-bytes" and encoded != sorted(encoded):
                    raise InterfaceError(
                        f"{where}: canonical unique list is unsorted or duplicated"
                    )
                elif order == "manifest-path":
                    try:
                        paths = [item["path"] for item in value]
                    except (KeyError, TypeError) as error:
                        raise InterfaceError(
                            f"{where}: malformed manifest path collection"
                        ) from error
                    if paths != sorted(paths) or len(paths) != len(set(paths)):
                        raise InterfaceError(
                            f"{where}: manifest paths are unsorted or duplicated"
                        )
        elif kind == "option":
            if not isinstance(value, dict) or list(value) not in (["tag"], ["tag", "value"]):
                raise InterfaceError(f"{where}: malformed option")
            if value["tag"] == "None" and list(value) == ["tag"]:
                return
            if value["tag"] == "Some" and list(value) == ["tag", "value"]:
                self.validate_descriptor(value["value"], desc["item"], where + ".value")
                return
            raise InterfaceError(f"{where}: malformed option arm")
        elif kind == "choice":
            matches = 0
            for item in desc["items"]:
                try:
                    self.validate_descriptor(value, item, where)
                except InterfaceError:
                    continue
                matches += 1
            if matches != 1:
                raise InterfaceError(
                    f"{where}: expected exactly one closed scalar choice"
                )
        else:
            raise InterfaceError(f"{where}: unsupported descriptor kind {kind!r}")

    def validate_record(self, value: Any, name: str, where: str = "$") -> None:
        try:
            rows = self.records[name]["fields"]
        except KeyError as error:
            raise InterfaceError(f"unknown root record {name}") from error
        expected = [row["name"] for row in rows]
        if not isinstance(value, dict) or list(value) != expected:
            actual = list(value) if isinstance(value, dict) else type(value).__name__
            raise InterfaceError(f"{where}: {name} fields/order {actual}, expected {expected}")
        for row in rows:
            self.validate_descriptor(value[row["name"]], row["type"], where + "." + row["name"])

    def validate_union(self, value: Any, name: str, where: str = "$") -> None:
        if (
            not isinstance(value, dict)
            or not value
            or list(value)[0] != "tag"
            or not isinstance(value.get("tag"), str)
        ):
            raise InterfaceError(f"{where}: {name} must be a tag-first object")
        try:
            variants = {row["tag"]: row for row in self.unions[name]["variants"]}
        except KeyError as error:
            raise InterfaceError(f"unknown root union {name}") from error
        if value["tag"] not in variants:
            raise InterfaceError(f"{where}: unknown {name} tag {value['tag']!r}")
        variant = variants[value["tag"]]
        if variant["shape"] == "nullary":
            if list(value) != ["tag"]:
                raise InterfaceError(f"{where}: nullary arm has extra fields")
        elif variant["shape"] == "args":
            arguments = value.get("args")
            if list(value) != ["tag", "args"] or not isinstance(arguments, list) or len(arguments) != len(variant["args"]):
                raise InterfaceError(f"{where}: malformed positional arm")
            for index, desc in enumerate(variant["args"]):
                self.validate_descriptor(arguments[index], desc, f"{where}.args[{index}]")
        else:
            rows = variant["fields"]
            expected = ["tag"] + [row["name"] for row in rows]
            if list(value) != expected:
                raise InterfaceError(f"{where}: field arm order mismatch")
            for row in rows:
                self.validate_descriptor(value[row["name"]], row["type"], where + "." + row["name"])

    def validate_root(self, value: Any, root_type: str) -> None:
        if self.distribution is not None:
            validate_schema_root(value, root_type, self.distribution)
        if root_type in self.records:
            self.validate_record(value, root_type)
        elif root_type in self.unions:
            self.validate_union(value, root_type)
        else:
            raise InterfaceError(f"unknown root type {root_type!r}")

    @staticmethod
    def _append_semantic_failure(failures: list[str], rule: str) -> None:
        if rule not in failures:
            failures.append(rule)

    @staticmethod
    def _exact_digest(value: Any) -> str:
        return sha256(canonical_bytes(value))

    def _semantic_reference_decision(self) -> Any:
        """Return the package-owned valid decision used as a shape oracle.

        The deterministic vector is part of the digest-locked SPS interface
        package.  Using it here keeps opaque-payload field inventory and
        identity-field associations out of the harness source; it does not
        replace any semantic predicate below.
        """

        cached = getattr(self, "_semantic_reference_decision_cache", None)
        if cached is not None:
            return cached
        if self.distribution is None:
            raise InterfaceError(
                "semantic validation requires a complete SPS distribution"
            )
        path = (
            self.distribution
            / "vectors"
            / "canonical-valid"
            / "aggregation-decision.v2.json"
        )
        try:
            reference = require_canonical(path.read_bytes())
        except OSError as error:
            raise InterfaceError(
                "SPS package omits the semantic reference decision"
            ) from error
        self.validate_record(reference, "AggregationDecisionV2")
        setattr(self, "_semantic_reference_decision_cache", reference)
        return reference

    def _semantic_reference_evidence(self) -> Any:
        return self._semantic_reference_decision()["identityEvidence"]

    def _record_literal(self, record_name: str, field_name: str) -> Any:
        for row in self.records[record_name]["fields"]:
            if row["name"] == field_name and row["type"].get("kind") == "literal":
                return row["type"]["value"]
        raise InterfaceError(
            f"registry omits literal {record_name}.{field_name}"
        )

    def _ordered_record(self, record_name: str, members: dict[str, Any]) -> Any:
        fields = self.record_fields(record_name)
        if set(fields) != set(members):
            raise InterfaceError(
                f"semantic constructor does not cover {record_name}"
            )
        return OrderedDict((field, members[field]) for field in fields)

    def _identity_envelope_fields(self) -> tuple[str, ...]:
        fields: list[str] = []
        for row in self.records["ArtifactIdentityEvidenceV2"]["fields"]:
            desc = row["type"]
            if desc.get("kind") != "record":
                continue
            record_name = desc["name"]
            if self.record_fields(record_name) == (
                "formatId", "canonicalBytes", "sha256"
            ):
                fields.append(row["name"])
        return tuple(fields)

    def _identity_envelope_digest_fields(self) -> dict[str, str]:
        evidence = self._semantic_reference_evidence()
        identity = evidence["artifactIdentity"]
        result: dict[str, str] = {}
        for field_name in self._identity_envelope_fields():
            digest = evidence[field_name]["sha256"]
            matches = [
                name
                for name, value in identity.items()
                if name.endswith("Digest") and value == digest
            ]
            if len(matches) > 1:
                raise InterfaceError(
                    f"ambiguous identity binding for {field_name}"
                )
            if matches:
                result[field_name] = matches[0]
        return result

    def _exact_evidence_digest_fields(self) -> dict[str, str]:
        evidence = self._semantic_reference_evidence()
        identity = evidence["artifactIdentity"]
        excluded = {
            "artifactIdentity", "canonicalBitcode", "proofConfiguration",
            *self._identity_envelope_fields(),
        }
        result: dict[str, str] = {}
        evidence_fields = self.record_fields("ArtifactIdentityEvidenceV2")
        for field_name in evidence_fields:
            if field_name in excluded or field_name not in evidence:
                continue
            digest = self._exact_digest(evidence[field_name])
            matches = [
                name
                for name, value in identity.items()
                if name.endswith("Digest") and value == digest
            ]
            if len(matches) == 1:
                result[field_name] = matches[0]
            elif len(matches) > 1:
                raise InterfaceError(
                    f"ambiguous exact evidence binding for {field_name}"
                )
        return result

    def _decode_envelope(self, envelope: Any) -> Any:
        try:
            return require_canonical(bytes.fromhex(envelope["canonicalBytes"]))
        except (KeyError, TypeError, ValueError):
            return None

    def _reference_payloads(self) -> dict[str, Any]:
        evidence = self._semantic_reference_evidence()
        return {
            field_name: self._decode_envelope(evidence[field_name])
            for field_name in self._identity_envelope_fields()
        }

    @staticmethod
    def _envelope_is_exact(value: Any) -> bool:
        try:
            raw = bytes.fromhex(value["canonicalBytes"])
            require_canonical(raw)
        except (KeyError, TypeError, ValueError):
            return False
        return sha256(raw) == value["sha256"]

    def _payload_collections_are_typed(
        self, field_name: str, value: Any
    ) -> bool:
        lint_classes = self.enum_values("ReleasePolicyLintClass")
        if field_name == "llvmBuild":
            return _sps_llvm_build_payload_is_typed(value)
        if field_name == "spsBuild":
            return _sps_sps_build_payload_is_typed(value)
        if field_name == "passTrace":
            return _sps_pass_trace_payload_is_typed(value)
        if field_name == "targetConfiguration":
            return _sps_target_configuration_payload_is_typed(value)
        if field_name == "policy":
            return _sps_policy_payload_is_typed(value, lint_classes)
        if field_name == "abi":
            return _sps_abi_payload_is_typed(value)
        if field_name == "contractTable":
            return _sps_contract_payload_is_typed(value)
        if field_name == "placementTable":
            return _sps_placement_payload_is_typed(value)
        if field_name == "aliasTopology":
            return _sps_alias_topology_payload_is_typed(value)
        if field_name == "allocaSizeBindings":
            return (
                value["formatId"]
                == "SPS-Alloca-Size-Bindings-Digest-Preimage-v2"
                and _sps_typed_map_rows(
                    value["bindings"], _sps_typed_id, _sps_typed_policy_expr
                )
            )
        if field_name == "publicBounds":
            return (
                value["formatId"] == "SPS-Public-Bounds-Digest-Preimage-v2"
                and _sps_typed_map_rows(
                    value["bounds"], _sps_typed_id, _sps_typed_policy_expr
                )
            )
        if field_name == "preconditions":
            return (
                value["formatId"] == "SPS-Preconditions-Digest-Preimage-v2"
                and isinstance(value["predicates"], list)
                and _sps_typed_canonical_unique_list(value["predicates"])
                and all(
                    _sps_typed_policy_expr(item)
                    for item in value["predicates"]
                )
            )
        if field_name == "stableIRBindings":
            return _sps_stable_ir_payload_is_typed(value)
        if field_name == "latencyClassTable":
            return _sps_latency_class_payload_is_typed(value)
        if field_name == "timingEnvironment":
            return _sps_timing_environment_payload_is_typed(value)
        if field_name == "entryScope":
            return _sps_entry_scope_payload_is_typed(value)
        if field_name == "profileConfiguration":
            return _sps_profile_configuration_payload_is_typed(value)
        if field_name == "globalRegionTable":
            return _sps_global_region_payload_is_typed(value)
        if field_name == "preflightTaskSchedule":
            return _sps_preflight_schedule_payload_is_typed(value)
        if field_name == "stackProtectorPreflight":
            return all(_sps_typed_id_list(rows) for rows in value.values())
        if field_name == "policyReviewConfiguration":
            threshold = value["capacityWarningThresholdBits"]
            return (
                isinstance(threshold, dict)
                and list(threshold) == ["numerator", "denominator"]
                and _sps_typed_nat(threshold["numerator"])
                and _sps_typed_pos(threshold["denominator"])
                and value["enabledLintSet"] == list(lint_classes)
                and _sps_typed_digest(value["versionAndSemantics"])
            )
        return True

    def _release_type_widths(self, value: Any) -> list[int]:
        if not isinstance(value, dict) or list(value) != ["tag", "args"]:
            raise ValueError("release type must be a tag/args constructor")
        arguments = value["args"]
        if value["tag"] == "BVType":
            if (
                not isinstance(arguments, list)
                or len(arguments) != 2
                or isinstance(arguments[0], bool)
                or not isinstance(arguments[0], int)
                or arguments[0] < 1
                or arguments[1] not in {"LittleEndian", "BigEndian"}
            ):
                raise ValueError("malformed BVType")
            return [arguments[0]]
        if value["tag"] == "TupleType":
            if not isinstance(arguments, list) or len(arguments) != 1:
                raise ValueError("malformed TupleType")
            rows = arguments[0]
            if not isinstance(rows, list) or not rows:
                raise ValueError("TupleType is empty")
            field_ids: list[str] = []
            widths: list[int] = []
            for row in rows:
                if (
                    not isinstance(row, list)
                    or len(row) != 2
                    or not _sps_typed_id(row[0])
                ):
                    raise ValueError("malformed TupleType field")
                field_ids.append(row[0])
                widths.extend(self._release_type_widths(row[1]))
            if len(field_ids) != len(set(field_ids)):
                raise ValueError("duplicate TupleType field ID")
            return widths
        raise ValueError("unknown release type constructor")

    def _release_table_entries(self, value: Any) -> list[tuple[Any, list[int]]]:
        reference = self._reference_payloads()["releaseTable"]
        expression_semantics = reference["expressionSemantics"]
        if (
            not isinstance(value, dict)
            or list(value) != ["formatId", "expressionSemantics", "entries"]
            or value["formatId"] != reference["formatId"]
            or value["expressionSemantics"] != expression_semantics
            or not isinstance(value["entries"], list)
        ):
            raise ValueError("malformed release-table envelope")
        result: list[tuple[Any, list[int]]] = []
        release_ids: list[str] = []
        for entry in value["entries"]:
            if not _sps_typed_release_spec(entry, expression_semantics):
                raise ValueError("malformed typed release specification")
            release_ids.append(entry["releaseId"])
            result.append((entry, self._release_type_widths(entry["type"])))
        if release_ids != sorted(release_ids) or len(release_ids) != len(
            set(release_ids)
        ):
            raise ValueError("release table IDs are unsorted or duplicated")
        return result

    def _canonical_payload_is_bounded(
        self, field_name: str, value: Any
    ) -> bool:
        reference_payloads = self._reference_payloads()
        if field_name == "releaseTable":
            try:
                self._release_table_entries(value)
            except (KeyError, TypeError, ValueError):
                return False
            return True
        if field_name not in reference_payloads:
            return False
        template = reference_payloads[field_name]
        if field_name == "interfaceManifest":
            return value == template
        if not _sps_payload_shape_matches(value, template):
            return False
        if not self._payload_collections_are_typed(field_name, value):
            return False
        exact_fields = {
            "transitionRuleTable", "observationSemantics",
            "fpNaNPayloadSemantics", "policyExpressionSemantics",
            "ponfSemantics", "interfaceManifest",
        }
        if field_name in exact_fields and value != template:
            return False
        if "formatId" in template and value["formatId"] != template["formatId"]:
            return False
        if field_name == "llvmBuild":
            return (
                value["tag"] == template["tag"]
                and value["commit"] == template["commit"]
            )
        if field_name == "spsBuild":
            return (
                re.fullmatch(r"[0-9a-f]{40}", value["patchCommit"])
                is not None
                and value["transitionRuleTableDigest"]
                == self._semantic_reference_evidence()["transitionRuleTable"][
                    "sha256"
                ]
            )
        if field_name == "targetConfiguration":
            return all(
                value[key] == template[key]
                for key in [
                    "ltoMode", "sanitizerMode", "instructionSelector",
                    "fastISelEnabled", "globalISelEnabled",
                    "globalISelFallbackEnabled",
                ]
            )
        if field_name == "profileConfiguration":
            return all(
                value[key] == template[key]
                for key in [
                    "floatTypes", "moduleFlagPolicy",
                    "codegenAttributePolicy", "stackProtectorPolicy",
                    "globalRegionTableDigest", "preflightTaskScheduleDigest",
                    "publicAliasTopologyDigest",
                ]
            )
        if field_name == "policyReviewConfiguration":
            return value["enabledLintSet"] == list(
                self.enum_values("ReleasePolicyLintClass")
            )
        if field_name == "preflightTaskSchedule":
            return value["formatId"] == template["formatId"]
        return True

    def _release_binding_failures(
        self,
        bindings: Any,
        machine_map: Any | None = None,
        release_table_value: Any | None = None,
    ) -> list[str]:
        failures: list[str] = []
        rows = bindings["rows"]
        keys = {
            "release": [row["releaseId"] for row in rows],
            "site": [row["siteId"] for row in rows],
            "wrapper": [
                row["implementation"]["wrapperFunction"] for row in rows
            ],
            "instruction": [
                row["implementation"]["emitMarkerInstructionId"]
                for row in rows
            ],
        }
        if any(len(values) != len(set(values)) for values in keys.values()):
            self._append_semantic_failure(failures, "XF-INTRINSIC-001")
        if any(not row["flattenedIntegerWidths"] for row in rows):
            self._append_semantic_failure(failures, "XF-INTRINSIC-001")
        if release_table_value is not None:
            entries = self._release_table_entries(release_table_value)
            if len(entries) != len(rows):
                self._append_semantic_failure(failures, "XF-INTRINSIC-001")
            else:
                for binding, (entry, widths) in zip(rows, entries):
                    if (
                        binding["releaseId"] != entry["releaseId"]
                        or binding["siteId"] != entry["site"]
                        or binding["implementation"]
                        != entry["implementation"]
                        or binding["flattenedIntegerWidths"] != widths
                        or binding["releaseSpecV2Digest"]
                        != self._exact_digest(entry)
                    ):
                        self._append_semantic_failure(
                            failures, "XF-INTRINSIC-001"
                        )
        if machine_map is not None:
            map_rows = machine_map["rows"]
            map_keys = {
                "instruction": [
                    row["emitMarkerInstructionId"] for row in map_rows
                ],
                "pseudo": [row["mirPseudoId"] for row in map_rows],
                "boundary": [row["p4BoundaryId"] for row in map_rows],
            }
            if any(
                len(values) != len(set(values))
                for values in map_keys.values()
            ):
                self._append_semantic_failure(failures, "XF-INTRINSIC-001")
            if set(keys["instruction"]) != set(map_keys["instruction"]):
                self._append_semantic_failure(failures, "XF-INTRINSIC-001")
        return failures

    def _query_scope_is_exact(self, query: Any) -> bool:
        kind = query["queryKind"]["tag"]
        coalition_kinds = {
            "AuditAll", "HighVariation", "CouplingTotality",
            "CouplingFiberTotal", "CouplingSymmetry",
            "CouplingSchedulePreservation",
        }
        release_kinds = {"ReleaseConformance", "ReleaseActivation"}
        component_kinds = {"HighVariation"}
        relation_kinds = {
            "CouplingTotality", "CouplingFiberTotal", "CouplingSymmetry",
            "CouplingSchedulePreservation",
        }
        return (
            query["entryScope"]["tag"] == "Some"
            and (
                query["coalitionScope"]["tag"] == "ConcreteCoalition"
            )
            == (kind in coalition_kinds)
            and (query["releaseScope"]["tag"] == "Some")
            == (kind in release_kinds)
            and (query["componentScope"]["tag"] == "Some")
            == (kind in component_kinds)
            and (query["relationScope"]["tag"] == "Some")
            == (kind in relation_kinds)
        )

    @staticmethod
    def _schedule_kind_order() -> tuple[str, ...]:
        # This is a prose-level execution order, not QueryKindV2 wire order.
        return (
            "AuditAll", "ReleaseActivation", "ReleaseConformance",
            "AdmissionNonempty", "LLVMDefinedness", "Initialization",
            "BoundAdequacy", "StructuralAlloca", "OutputClosure",
            "HighVariation", "CouplingTotality", "CouplingFiberTotal",
            "CouplingSymmetry", "CouplingSchedulePreservation",
        )

    def _query_schedule_is_complete(self, queries: Any) -> bool:
        if not isinstance(queries, list) or not queries:
            return False
        kinds = [query["queryKind"]["tag"] for query in queries]
        query_kinds = set(self.union_variants("QueryKindV2"))
        if any(kind not in query_kinds for kind in kinds) or not all(
            self._query_scope_is_exact(query) for query in queries
        ):
            return False
        order = self._schedule_kind_order()
        if set(query_kinds) != set(order):
            raise InterfaceError(
                "QueryKindV2 and semantic schedule order disagree"
            )
        expected = sorted(
            queries,
            key=lambda query: (
                order.index(query["queryKind"]["tag"]),
                canonical_bytes(query),
            ),
        )
        return queries == expected and len(
            {canonical_bytes(query) for query in queries}
        ) == len(queries)

    @staticmethod
    def _canonical_map(rows: Any) -> OrderedDict[Any, Any]:
        return OrderedDict((row["key"], row["value"]) for row in rows)

    @staticmethod
    def _option_id(value: str | None) -> OrderedDict[str, Any]:
        if value is None:
            return OrderedDict([("tag", "None")])
        return OrderedDict([("tag", "Some"), ("value", value)])

    def _query_descriptor(
        self,
        kind: str,
        *,
        entry_id: str,
        coalition_id: str | None = None,
        release_id: str | None = None,
        component_id: str | None = None,
        relation_id: str | None = None,
    ) -> OrderedDict[str, Any]:
        coalition_kinds = {
            "AuditAll", "HighVariation", "CouplingTotality",
            "CouplingFiberTotal", "CouplingSymmetry",
            "CouplingSchedulePreservation",
        }
        release_kinds = {"ReleaseConformance", "ReleaseActivation"}
        component_kinds = {"HighVariation"}
        relation_kinds = {
            "CouplingTotality", "CouplingFiberTotal", "CouplingSymmetry",
            "CouplingSchedulePreservation",
        }
        coalition_scope: Any = OrderedDict([("tag", "None")])
        if kind in coalition_kinds:
            coalition_scope = OrderedDict([
                ("tag", "ConcreteCoalition"),
                ("coalitionId", coalition_id),
            ])
        return self._ordered_record(
            "QueryDescriptorV2",
            {
                "queryKind": OrderedDict([("tag", kind)]),
                "entryScope": self._option_id(entry_id),
                "coalitionScope": coalition_scope,
                "releaseScope": self._option_id(
                    release_id if kind in release_kinds else None
                ),
                "componentScope": self._option_id(
                    component_id if kind in component_kinds else None
                ),
                "relationScope": self._option_id(
                    relation_id if kind in relation_kinds else None
                ),
            },
        )

    @staticmethod
    def _derived_adversary_coalitions(
        maximal_coalitions: list[list[str]],
    ) -> list[tuple[str, list[str]]]:
        """Return the canonical downward closure of the authored maxima."""
        coalition_sets: set[tuple[str, ...]] = set()
        for maximal in maximal_coalitions:
            principals = sorted(set(maximal))
            for mask in range(1 << len(principals)):
                coalition_sets.add(tuple(
                    principal
                    for index, principal in enumerate(principals)
                    if mask & (1 << index)
                ))
        coalitions = sorted(
            (list(principals) for principals in coalition_sets),
            key=canonical_bytes,
        )
        return [
            (sha256(canonical_bytes(principals)), principals)
            for principals in coalitions
        ]

    def _required_query_schedule(
        self, canonical_inputs: dict[str, Any]
    ) -> OrderedDict[str, Any]:
        names = (
            "policy", "abi", "releaseTable", "contractTable",
            "entryScope", "timingEnvironment",
        )
        decoded = {
            name: require_canonical(
                bytes.fromhex(canonical_inputs[name]["canonicalBytes"])
            )
            for name in names
        }
        policy = decoded["policy"]
        entries = [row["key"] for row in policy["entries"]]
        coalitions = self._derived_adversary_coalitions(
            policy["maximalAdversaryCoalitions"]
        )
        components = self._canonical_map(policy["components"])
        member_visibility = self._canonical_map(
            policy["componentVisibility"]["memberVisible"]
        )
        world_visible = set(policy["componentVisibility"]["worldVisible"])
        joint_visibility = policy["componentVisibility"][
            "minimallyJointVisible"
        ]
        release_entries = {
            entry["releaseId"]: entry
            for entry in decoded["releaseTable"]["entries"]
        }
        entry_scopes = {
            row["entryId"]: row for row in decoded["entryScope"]["rows"]
        }
        queries: list[OrderedDict[str, Any]] = []
        for entry_id in entries:
            for coalition_id, _principals in coalitions:
                queries.append(
                    self._query_descriptor(
                        "AuditAll", entry_id=entry_id,
                        coalition_id=coalition_id,
                    )
                )
        for entry_id in entries:
            for release_id, release in release_entries.items():
                claims = self._canonical_map(release["activationClaims"])
                if entry_id in claims:
                    queries.append(
                        self._query_descriptor(
                            "ReleaseActivation", entry_id=entry_id,
                            release_id=release_id,
                        )
                    )
                    if claims[entry_id]["tag"] != "NotApplicable":
                        queries.append(
                            self._query_descriptor(
                                "ReleaseConformance", entry_id=entry_id,
                                release_id=release_id,
                            )
                        )
        for kind in (
            "AdmissionNonempty", "LLVMDefinedness", "Initialization",
            "BoundAdequacy", "StructuralAlloca", "OutputClosure",
        ):
            queries.extend(
                self._query_descriptor(kind, entry_id=entry_id)
                for entry_id in entries
            )
        for entry_id in entries:
            for coalition_id, principals in coalitions:
                principal_set = set(principals)
                for component_id, component in components.items():
                    if entry_id not in component["applicableEntries"]:
                        continue
                    visible = component_id in world_visible or any(
                        component_id in member_visibility.get(principal, [])
                        for principal in principals
                    ) or any(
                        visible_component == component_id
                        and set(joint_principals).issubset(principal_set)
                        for joint_principals, visible_component
                        in joint_visibility
                    )
                    if not visible:
                        queries.append(
                            self._query_descriptor(
                                "HighVariation", entry_id=entry_id,
                                coalition_id=coalition_id,
                                component_id=component_id,
                            )
                        )
        for contract in decoded["contractTable"]["contracts"]:
            relation_rows: list[tuple[str, str]] = []
            boundaries = set(self._canonical_map(contract["occurrences"]))
            for row in contract["pairedChoiceCoupling"]:
                relation_rows.append(
                    (row["key"], row["value"]["relationId"])
                )
            for entry_id, scope in entry_scopes.items():
                if boundaries.intersection(scope["reachableBoundaryIds"]):
                    for coalition_id, relation_id in relation_rows:
                        for kind in (
                            "CouplingTotality", "CouplingFiberTotal",
                            "CouplingSymmetry",
                            "CouplingSchedulePreservation",
                        ):
                            queries.append(
                                self._query_descriptor(
                                    kind, entry_id=entry_id,
                                    coalition_id=coalition_id,
                                    relation_id=relation_id,
                                )
                            )
        for row in decoded["timingEnvironment"]["pairedChoiceCoupling"]:
            relation = row["value"]
            for entry_id in entries:
                for kind in (
                    "CouplingTotality", "CouplingFiberTotal",
                    "CouplingSymmetry", "CouplingSchedulePreservation",
                ):
                    queries.append(
                        self._query_descriptor(
                            kind, entry_id=entry_id,
                            coalition_id=row["key"],
                            relation_id=relation["relationId"],
                        )
                    )
        unique_queries = {
            canonical_bytes(query): query for query in queries
        }
        order = self._schedule_kind_order()
        ordered = sorted(
            unique_queries.values(),
            key=lambda query: (
                order.index(query["queryKind"]["tag"]),
                canonical_bytes(query),
            ),
        )
        return self._ordered_record(
            "RequiredQueryScheduleV2",
            {
                "formatId": self._record_literal(
                    "RequiredQueryScheduleV2", "formatId"
                ),
                "queries": ordered,
            },
        )

    def _proof_configuration_failures(self, value: Any) -> list[str]:
        failures: list[str] = []
        evidence = self._semantic_reference_evidence()
        if value["aggregationSemanticsDigest"] != self._exact_digest(
            evidence["aggregationSemantics"]
        ):
            self._append_semantic_failure(failures, "XF-IDENTITY-001")
        if value["replayAcceptanceSemanticsDigest"] != self._exact_digest(
            evidence["replayAcceptanceSemantics"]
        ):
            self._append_semantic_failure(failures, "XF-IDENTITY-001")
        if not self._query_schedule_is_complete(
            value["requiredQuerySchedule"]["queries"]
        ):
            self._append_semantic_failure(failures, "XF-IDENTITY-001")
        return failures

    def _identity_evidence_failures(self, value: Any) -> list[str]:
        failures: list[str] = []
        identity = value["artifactIdentity"]
        release_table_value: Any | None = None
        decoded_inputs: dict[str, Any] = {}
        if value["artifactIdentityDigest"] != self._exact_digest(identity):
            self._append_semantic_failure(failures, "XF-IDENTITY-001")
        bitcode = value["canonicalBitcode"]
        try:
            bitcode_raw = bytes.fromhex(bitcode["exactBytes"])
        except ValueError:
            bitcode_raw = b""
            self._append_semantic_failure(failures, "XF-IDENTITY-001")
        if (
            bitcode["sha256"] != sha256(bitcode_raw)
            or identity["canonicalBitcodeHash"] != bitcode["sha256"]
        ):
            self._append_semantic_failure(failures, "XF-IDENTITY-001")

        identity_bindings = self._identity_envelope_digest_fields()
        for field_name in self._identity_envelope_fields():
            envelope = value[field_name]
            if not self._envelope_is_exact(envelope):
                self._append_semantic_failure(failures, "XF-IDENTITY-001")
            identity_field = identity_bindings.get(field_name)
            if (
                identity_field is not None
                and identity[identity_field] != envelope["sha256"]
            ):
                self._append_semantic_failure(failures, "XF-IDENTITY-001")
            decoded = self._decode_envelope(envelope)
            if not self._canonical_payload_is_bounded(field_name, decoded):
                self._append_semantic_failure(failures, "XF-PAYLOAD-001")
            else:
                decoded_inputs[field_name] = decoded
                if field_name == "releaseTable":
                    release_table_value = decoded
                elif field_name == "interfaceManifest":
                    try:
                        self.validate_record(
                            decoded, "SPSConformanceInterfaceManifestV2"
                        )
                    except (InterfaceError, TypeError):
                        self._append_semantic_failure(
                            failures, "XF-PAYLOAD-001"
                        )

        proof = value["proofConfiguration"]
        if identity["proofConfigurationDigest"] != self._exact_digest(proof):
            self._append_semantic_failure(failures, "XF-IDENTITY-001")
        for rule in self._proof_configuration_failures(proof):
            self._append_semantic_failure(failures, rule)

        exact_bindings = self._exact_evidence_digest_fields()
        for evidence_field, identity_field in exact_bindings.items():
            if identity[identity_field] != self._exact_digest(
                value[evidence_field]
            ):
                self._append_semantic_failure(failures, "XF-IDENTITY-001")
        if (
            proof["aggregationSemanticsDigest"]
            != identity["aggregationSemanticsDigest"]
            or proof["replayAcceptanceSemanticsDigest"]
            != identity["replayAcceptanceSemanticsDigest"]
        ):
            self._append_semantic_failure(failures, "XF-IDENTITY-001")
        derivation = value["queryScheduleDerivation"]
        digest_bindings = {
            "policyDigest": "policyDigest",
            "abiDigest": "abiDigest",
            "releaseDigest": "releaseDigest",
            "contractDigest": "contractDigest",
            "entryScopeDigest": "entryScopeDigest",
            "timingEnvironmentContractDigest":
                "timingEnvironmentContractDigest",
            "profileConfigurationDigest": "profileConfigurationDigest",
        }
        if any(
            derivation[derivation_field] != identity[identity_field]
            for derivation_field, identity_field in digest_bindings.items()
        ) or derivation["requiredQuerySchedule"] != proof[
            "requiredQuerySchedule"
        ]:
            self._append_semantic_failure(failures, "XF-IDENTITY-001")
        schedule_input_names = (
            "policy", "abi", "releaseTable", "contractTable",
            "entryScope", "timingEnvironment",
        )
        if all(name in decoded_inputs for name in schedule_input_names):
            schedule_inputs = OrderedDict(
                (name, value[name]) for name in schedule_input_names
            )
            try:
                recomputed = self._required_query_schedule(schedule_inputs)
            except (KeyError, TypeError, ValueError):
                self._append_semantic_failure(failures, "XF-PAYLOAD-001")
            else:
                if (
                    proof["requiredQuerySchedule"] != recomputed
                    or derivation["requiredQuerySchedule"] != recomputed
                ):
                    self._append_semantic_failure(
                        failures, "XF-IDENTITY-001"
                    )
        required_payloads = {
            "policy", "abi", "releaseTable", "aliasTopology",
            "allocaSizeBindings", "transitionRuleTable",
            "policyReviewConfiguration", "profileConfiguration",
            "publicBounds", "preconditions", "policyExpressionSemantics",
            "globalRegionTable", "preflightTaskSchedule", "spsBuild",
        }
        if required_payloads.issubset(decoded_inputs):
            policy = decoded_inputs["policy"]
            abi = decoded_inputs["abi"]
            profile = decoded_inputs["profileConfiguration"]
            if (
                decoded_inputs["policyReviewConfiguration"]
                != policy["releasePolicyReviewConfig"]
                or decoded_inputs["publicBounds"]["bounds"]
                != policy["publicBounds"]
                or decoded_inputs["preconditions"]["predicates"]
                != policy["preconditions"]
                or decoded_inputs["allocaSizeBindings"]["bindings"]
                != policy["allocaSizeBindings"]
                or decoded_inputs["aliasTopology"]["selectedTopologyIds"]
                != policy["publicAliasTopologyIds"]
                or decoded_inputs["aliasTopology"]["bindings"]
                != abi["aliasTopologyBindings"]
                or decoded_inputs["policyExpressionSemantics"]
                != decoded_inputs["releaseTable"]["expressionSemantics"]
                or any(
                    entry[0]["deterministicSemantics"]
                    != decoded_inputs["policyExpressionSemantics"]
                    for entry in self._release_table_entries(
                        decoded_inputs["releaseTable"]
                    )
                )
                or decoded_inputs["spsBuild"]["transitionRuleTableDigest"]
                != value["transitionRuleTable"]["sha256"]
                or profile["globalRegionTableDigest"]
                != value["globalRegionTable"]["sha256"]
                or profile["preflightTaskScheduleDigest"]
                != value["preflightTaskSchedule"]["sha256"]
                or profile["publicAliasTopologyDigest"]
                != value["aliasTopology"]["sha256"]
            ):
                self._append_semantic_failure(failures, "XF-IDENTITY-001")
        for rule in self._release_binding_failures(
            value["releaseMarkerBindings"],
            value["releaseMarkerMachineMap"],
            release_table_value,
        ):
            self._append_semantic_failure(failures, rule)
        return failures

    @staticmethod
    def _report_receipts(report: Any) -> list[str]:
        receipts = [report["runEvidence"]["receiptId"]]
        status = report["modelStatus"]
        if status["tag"] == "Counterexample":
            receipts.append(status["args"][0])
        for row in report["queryResults"]:
            outcome = row["outcome"]
            if outcome["tag"] == "NotConstructedV2":
                receipts.append(outcome["protectedEvidence"]["receiptId"])
            else:
                receipts.append(
                    outcome["args"][0]["protectedEvidence"]["receiptId"]
                )
        receipts.extend(
            row["protectedEvidence"]["receiptId"]
            for row in report["preflightSummaries"]
        )
        return receipts

    @classmethod
    def _contains_stale_v2_carrier_reason(cls, value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("reasonClassId") == "ReleaseConformanceMismatch":
                return True
            return any(
                cls._contains_stale_v2_carrier_reason(item)
                for item in value.values()
            )
        if isinstance(value, list):
            return any(
                cls._contains_stale_v2_carrier_reason(item) for item in value
            )
        return False

    @staticmethod
    def _query_disposition_is_legal(query: Any, artifact: Any) -> bool:
        kind = query["queryKind"]["tag"]
        raw = artifact["rawSolverResult"]
        disposition = artifact["queryDisposition"]
        tag = disposition["tag"]
        existential = {"AdmissionNonempty", "HighVariation"}
        safety = kind not in {*existential, "ReleaseActivation"}
        if raw == "SAT":
            if safety:
                return tag == "CandidateOnly"
            return tag in {"ValidatedExistentialWitness", "Unknown"}
        if raw == "UNSAT":
            if safety:
                return tag == "Discharged"
            if kind == "AdmissionNonempty":
                return (
                    tag == "Unknown"
                    and disposition["args"][0]["reasonClassId"]
                    == "VacuousAdmission"
                )
            if kind == "HighVariation":
                return tag in {"ConstrainedOrUnexercised", "Unknown"}
            return tag in {"Discharged", "Unknown"}
        return raw == "UNKNOWN" and tag == "Unknown"

    @classmethod
    def _query_result_closes_gate(cls, query: Any, outcome: Any) -> bool:
        if outcome["tag"] != "Constructed":
            return False
        artifact = outcome["args"][0]
        if not cls._query_disposition_is_legal(query, artifact):
            return False
        kind = query["queryKind"]["tag"]
        raw = artifact["rawSolverResult"]
        tag = artifact["queryDisposition"]["tag"]
        if kind in {"AdmissionNonempty", "HighVariation", "ReleaseActivation"}:
            if raw == "SAT":
                return tag == "ValidatedExistentialWitness"
            if kind == "HighVariation" and raw == "UNSAT":
                return tag == "ConstrainedOrUnexercised"
            if kind == "ReleaseActivation" and raw == "UNSAT":
                return tag == "Discharged"
            return False
        return raw == "UNSAT" and tag == "Discharged"

    @classmethod
    def _report_model_gates_closed(cls, report: Any) -> bool:
        queries = report["querySchedule"]["queries"]
        results = report["queryResults"]
        return (
            len(queries) == len(results)
            and all(
                row["queryOrdinal"] == index
                and cls._query_result_closes_gate(
                    queries[index], row["outcome"]
                )
                for index, row in enumerate(results)
            )
            and report["policyReviewStatus"]["tag"] != "Incomplete"
        )

    def _public_report_failures(self, report: Any) -> list[str]:
        failures: list[str] = []
        schedule = report["querySchedule"]
        results = report["queryResults"]
        schedule_ok = (
            schedule["artifactIdentityDigest"]
            == report["artifactIdentityDigest"]
            and schedule["proofConfigurationDigest"]
            == report["proofConfigurationDigest"]
            and report["queryScheduleDigest"] == self._exact_digest(schedule)
            and len(schedule["queries"]) == len(results)
            and [row["queryOrdinal"] for row in results]
            == list(range(len(results)))
            and self._query_schedule_is_complete(schedule["queries"])
        )
        for index, row in enumerate(results):
            if row["outcome"]["tag"] == "Constructed":
                artifact = row["outcome"]["args"][0]
                schedule_ok = schedule_ok and (
                    artifact["proofConfigurationDigest"]
                    == report["proofConfigurationDigest"]
                )
                if index < len(schedule["queries"]):
                    schedule_ok = schedule_ok and (
                        self._query_disposition_is_legal(
                            schedule["queries"][index], artifact
                        )
                    )
        schedule_ok = schedule_ok and all(
            row["artifactIdentityDigest"]
            == report["artifactIdentityDigest"]
            for row in report["preflightSummaries"]
        )
        review = report["releasePolicyReview"]
        schedule_ok = schedule_ok and (
            review["artifactIdentityDigest"]
            == report["artifactIdentityDigest"]
            and review["status"] == report["policyReviewStatus"]
        )
        if (
            report["modelStatus"]["tag"] == "Proved"
            and not self._report_model_gates_closed(report)
        ):
            schedule_ok = False
        if not schedule_ok or self._contains_stale_v2_carrier_reason(report):
            self._append_semantic_failure(failures, "XF-REPORT-003")
        receipts = self._report_receipts(report)
        if len(receipts) != len(set(receipts)):
            self._append_semantic_failure(failures, "XF-REPORT-002")
        return failures

    def _accepted_replay_failures(self, value: Any) -> list[str]:
        failures: list[str] = []
        if value["finalReceiptId"] != value["protectedEvidence"]["receiptId"]:
            self._append_semantic_failure(failures, "XF-REPLAY-002")
        return failures

    def _aggregation_input_failures(self, value: Any) -> list[str]:
        failures: list[str] = []
        accepted = value["acceptedBadReplay"]["tag"] == "Some"
        replay = value["acceptedBadReplay"].get("value")
        invalidating = any(
            row["scope"] == "ReplayInvalidating" for row in value["blockers"]
        )
        if accepted and invalidating:
            self._append_semantic_failure(failures, "XF-REPLAY-001")
        if accepted:
            for rule in self._accepted_replay_failures(replay):
                self._append_semantic_failure(failures, rule)
            if (
                replay["artifactIdentityDigest"]
                != value["artifactIdentityDigest"]
                or replay["proofConfigurationDigest"]
                != value["proofConfigurationDigest"]
                or replay["queryScheduleDigest"]
                != value["queryScheduleDigest"]
            ):
                self._append_semantic_failure(failures, "XF-REPLAY-002")
        if (
            not accepted
            and not value["blockers"]
            and not value["allRequiredGatesClosed"]
        ):
            self._append_semantic_failure(failures, "XF-AGG-001")
        if value["blockers"] and value["allRequiredGatesClosed"]:
            self._append_semantic_failure(failures, "XF-AGG-001")
        wrong_reason_arm = any(
            (row["scope"] == "RunFinalization")
            != (row["reason"]["tag"] == "ReportingBlocker")
            for row in value["blockers"]
        )
        if wrong_reason_arm:
            self._append_semantic_failure(failures, "XF-AGG-002")
        return failures

    def _aggregation_outcome(self, value: Any) -> str:
        failures = self._aggregation_input_failures(value)
        if failures:
            raise ValueError("invalid aggregation input: " + ",".join(failures))
        finalization = [
            row
            for row in value["blockers"]
            if row["scope"] == "RunFinalization"
        ]
        if finalization:
            return "ReportingFailedV2"
        if value["acceptedBadReplay"]["tag"] == "Some":
            return "Counterexample"
        blockers = value["blockers"]
        if len(blockers) > 1:
            return "Unknown(OpenModelObligations)"
        if len(blockers) == 1:
            return (
                "Unknown("
                + blockers[0]["reason"]["reason"]["reasonClassId"]
                + ")"
            )
        if value["allRequiredGatesClosed"]:
            return "Proved"
        raise ValueError("aggregation input has neither result nor blocker")

    def _aggregation_decision_failures(self, value: Any) -> list[str]:
        evidence = value["identityEvidence"]
        identity = evidence["artifactIdentity"]
        input_value = value["input"]
        failures = self._identity_evidence_failures(evidence)
        for rule in self._aggregation_input_failures(input_value):
            self._append_semantic_failure(failures, rule)
        if (
            input_value["artifactIdentityDigest"]
            != evidence["artifactIdentityDigest"]
            or input_value["proofConfigurationDigest"]
            != identity["proofConfigurationDigest"]
        ):
            self._append_semantic_failure(failures, "XF-IDENTITY-001")
        run = value["runReport"]
        if run["tag"] == "CompletedV2":
            for rule in self._public_report_failures(run["report"]):
                self._append_semantic_failure(failures, rule)
            report = run["report"]
            review = report["releasePolicyReview"]
            if (
                review["policyDigest"] != identity["policyDigest"]
                or review["releaseDigest"] != identity["releaseDigest"]
                or review["policyReviewConfigurationDigest"]
                != identity["policyReviewConfigurationDigest"]
                or report["preflightTaskScheduleDigest"]
                != evidence["preflightTaskSchedule"]["sha256"]
            ):
                self._append_semantic_failure(failures, "XF-REPORT-003")
            if (
                report["querySchedule"]["queries"]
                != evidence["proofConfiguration"][
                    "requiredQuerySchedule"
                ]["queries"]
            ):
                self._append_semantic_failure(failures, "XF-REPORT-003")
            try:
                preflight = require_canonical(
                    bytes.fromhex(
                        evidence["preflightTaskSchedule"]["canonicalBytes"]
                    )
                )
                required_task_ids = [
                    task["taskId"] for task in preflight["tasks"]
                ]
            except (KeyError, TypeError, ValueError):
                required_task_ids = []
            summaries = report["preflightSummaries"]
            preflight_closed = (
                [row["taskId"] for row in summaries] == required_task_ids
                and all(
                    row["artifactIdentityDigest"]
                    == report["artifactIdentityDigest"]
                    for row in summaries
                )
            )
            computed_gates_closed = (
                self._report_model_gates_closed(report)
                and preflight_closed
            )
            if (
                input_value["allRequiredGatesClosed"]
                != computed_gates_closed
            ):
                self._append_semantic_failure(failures, "XF-AGG-001")
            accepted = input_value["acceptedBadReplay"]
            if accepted["tag"] == "Some":
                replay = accepted["value"]
                queries = report["querySchedule"]["queries"]
                if (
                    replay["queryOrdinal"] >= len(queries)
                    or queries[replay["queryOrdinal"]] != replay["query"]
                ):
                    self._append_semantic_failure(
                        failures, "XF-REPLAY-002"
                    )
        try:
            outcome = self._aggregation_outcome(input_value)
        except ValueError:
            return failures
        expected_matches = False
        if outcome == "ReportingFailedV2":
            expected_matches = run["tag"] == "ReportingFailedV2"
            if expected_matches:
                first = next(
                    row
                    for row in input_value["blockers"]
                    if row["scope"] == "RunFinalization"
                )
                expected_matches = (
                    run["report"]["reason"]
                    == first["reason"]["reason"]
                )
        elif run["tag"] == "CompletedV2":
            report = run["report"]
            expected_matches = (
                report["artifactIdentityDigest"]
                == input_value["artifactIdentityDigest"]
                and report["proofConfigurationDigest"]
                == input_value["proofConfigurationDigest"]
                and report["queryScheduleDigest"]
                == input_value["queryScheduleDigest"]
            )
            status = report["modelStatus"]
            if outcome == "Counterexample":
                replay = input_value["acceptedBadReplay"]["value"]
                expected_matches = expected_matches and status == OrderedDict([
                    ("tag", "Counterexample"),
                    ("args", [replay["finalReceiptId"]]),
                ])
                if not expected_matches:
                    self._append_semantic_failure(
                        failures, "XF-REPLAY-002"
                    )
            elif outcome == "Proved":
                expected_matches = expected_matches and status == OrderedDict([
                    ("tag", "Proved")
                ])
            elif outcome.startswith("Unknown("):
                reason = outcome.removeprefix("Unknown(").removesuffix(")")
                expected_matches = expected_matches and status == OrderedDict([
                    ("tag", "Unknown"),
                    ("args", [OrderedDict([("reasonClassId", reason)])]),
                ])
        if not expected_matches:
            self._append_semantic_failure(failures, "XF-AGG-001")
        return failures

    def semantic_failures(self, value: Any, root_type: str) -> list[str]:
        # Semantics mirror the CURRENT Rev4.1 source implementation in
        # SPS/interfaces/rev4.1/build_interfaces.py.  Schema validation must
        # precede this call, so the dispatch below only checks cross-field
        # obligations and opaque-payload closure.
        if root_type == "AcceptedBadReplayV2":
            return self._accepted_replay_failures(value)
        if root_type == "AggregationInputV2":
            return self._aggregation_input_failures(value)
        if root_type == "AggregationDecisionV2":
            return self._aggregation_decision_failures(value)
        if root_type == "ReleaseMarkerBindingArtifactV2":
            return self._release_binding_failures(value)
        if root_type == "ReleaseMarkerMachineMapV2":
            failures: list[str] = []
            rows = value["rows"]
            for field in (
                "emitMarkerInstructionId", "mirPseudoId", "p4BoundaryId"
            ):
                values = [row[field] for row in rows]
                if len(values) != len(set(values)):
                    self._append_semantic_failure(
                        failures, "XF-INTRINSIC-001"
                    )
            return failures
        if root_type == "ProofConfigurationV2":
            return self._proof_configuration_failures(value)
        if root_type == "ArtifactIdentityEvidenceV2":
            return self._identity_evidence_failures(value)
        if root_type == "SPSLLVMNFManifestV2":
            failures = self._identity_evidence_failures(
                value["artifactIdentityEvidence"]
            )
            identity = value["artifactIdentity"]
            evidence = value["artifactIdentityEvidence"]
            if identity != evidence["artifactIdentity"]:
                self._append_semantic_failure(failures, "XF-IDENTITY-001")
            for field in (
                "releaseMarkerBindingsDigest",
                "releaseMarkerMachineMapDigest",
                "intrinsicDefinitionDigest",
                "aggregationSemanticsDigest",
                "replayAcceptanceSemanticsDigest",
            ):
                if value[field] != identity[field]:
                    self._append_semantic_failure(
                        failures, "XF-IDENTITY-001"
                    )
            return failures
        if root_type == "SPSPublicReportV2":
            return self._public_report_failures(value)
        if root_type == "SPSRunReportV2" and value["tag"] == "CompletedV2":
            return self._public_report_failures(value["report"])
        return []


def _verify_refs(distribution: Path) -> None:
    documents = _schema_documents(distribution)
    for identifier, schema in documents.items():
        if schema.get("$schema") != SCHEMA_DRAFT:
            raise InterfaceError(f"invalid schema declaration: {identifier}")
        stack = [schema]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                ref = item.get("$ref")
                if isinstance(ref, str):
                    _resolve_schema_ref(documents, ref)
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)


def _verify_v2_only_distribution(
    distribution: Path, registry: Registry, listed: set[str]
) -> None:
    """Require the closed, uniformly V2 Rev4.1 package."""

    policy = registry.value.get("interfacePolicy")
    if not isinstance(policy, dict):
        raise InterfaceError("registry omits the V2-only interface policy")
    if list(policy) != ["currentRoots", "versionPolicy"]:
        raise InterfaceError("registry interface policy has an unexpected field")
    if policy.get("versionPolicy") != "v2-only":
        raise InterfaceError("registry does not declare the V2-only interface policy")
    current_roots = policy.get("currentRoots")
    if (
        not isinstance(current_roots, list)
        or "SPSRunReportV2" not in current_roots
        or not all(isinstance(root, str) and root.endswith("V2") for root in current_roots)
    ):
        raise InterfaceError("registry current roots are not uniformly V2")
    if registry.value.get("currentProfileId") != "SPS-LLVM-NF-v2":
        raise InterfaceError("registry current profile is not SPS-LLVM-NF-v2")


def verify_distribution(
    distribution: Path = VENDOR_ROOT,
    manifest_path: Path = VENDOR_MANIFEST,
) -> tuple[dict[str, Any], Registry]:
    manifest = require_canonical(manifest_path.read_bytes())
    if manifest.get("formatId") != "SPS-Interface-Manifest-v2":
        raise InterfaceError("unexpected SPS interface manifest format")
    listed: set[str] = set()
    for row in manifest.get("files", []):
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise InterfaceError("malformed interface manifest file row")
        relative = row["path"]
        if not isinstance(relative, str) or relative in listed:
            raise InterfaceError(f"duplicate or malformed manifest path: {relative!r}")
        path = (distribution / relative).resolve()
        try:
            path.relative_to(distribution.resolve())
        except ValueError as error:
            raise InterfaceError(f"manifest path escapes distribution: {relative}") from error
        raw = path.read_bytes()
        if sha256(raw) != row["sha256"]:
            raise InterfaceError(f"manifest digest mismatch: {relative}")
        require_canonical(raw)
        listed.add(relative)
    actual = {
        str(path.relative_to(distribution))
        for path in distribution.rglob("*")
        if path.is_file() and path.name != "upstream-manifest.json"
    }
    if actual != listed:
        raise InterfaceError(
            f"manifest file closure mismatch: listed={sorted(listed)}, actual={sorted(actual)}"
        )
    bundle = manifest.get("bundle", {})
    if bundle.get("path") not in listed:
        raise InterfaceError("manifest bundle is not in the file closure")
    if sha256((distribution / bundle["path"]).read_bytes()) != bundle.get("sha256"):
        raise InterfaceError("bundle manifest binding mismatch")
    _verify_refs(distribution)
    registry = Registry.from_path(distribution / "interface-registry.json")
    if registry.value["schemaSetId"] != manifest.get("schemaSetId"):
        raise InterfaceError("registry/manifest schemaSetId mismatch")
    _verify_v2_only_distribution(distribution, registry, listed)
    return manifest, registry


def verify_lock(manifest: dict[str, Any], registry: Registry) -> None:
    try:
        lock = strict_load(LOCK_PATH.read_bytes())
    except OSError as error:
        raise InterfaceError(f"missing SPS interface lock: {LOCK_PATH}") from error
    expected = {
        "formatId": "SPS-Harness-Interface-Lock-v2",
        "schemaSetId": manifest["schemaSetId"],
        "specRevision": manifest["specRevision"],
        "sourceRevision": manifest["sourceRevision"],
        "bundleSha256": manifest["bundle"]["sha256"],
        "registrySha256": sha256(canonical_bytes(registry.value)),
    }
    if lock != expected:
        raise InterfaceError(f"interface lock mismatch: expected {expected!r}, got {lock!r}")


def validate_vectors(distribution: Path, registry: Registry) -> None:
    catalog = require_canonical((distribution / "vectors" / "vector-catalog.json").read_bytes())
    for row in catalog["fileVectors"]:
        raw = (distribution / "vectors" / row["path"]).read_bytes()
        expectation = row["expectation"]
        try:
            value = require_canonical(raw)
            registry.validate_root(value, row["rootType"])
        except InterfaceError:
            if expectation == "schema-invalid":
                continue
            raise
        if expectation == "schema-invalid":
            raise InterfaceError(f"{row['path']}: expected schema rejection")
        failures = registry.semantic_failures(value, row["rootType"])
        if expectation == "semantic-invalid":
            if failures != [row["semanticRuleId"]]:
                raise InterfaceError(f"{row['path']}: semantic failures {failures}")
        elif failures:
            raise InterfaceError(f"{row['path']}: unexpected semantic failures {failures}")
    for row in catalog["rawCanonicalVectors"]:
        raw = base64.b64decode(row["encodingBase64"], validate=True)
        try:
            value = require_canonical(raw)
            registry.validate_root(value, row["rootType"])
        except InterfaceError:
            if row["expectation"] != "valid":
                continue
            raise
        if row["expectation"] != "valid":
            raise InterfaceError(f"raw {row['vectorId']}: expected rejection")


def verify_coupled_vendor(distribution: Path, manifest_path: Path) -> None:
    configured = os.environ.get("SPS_INTERFACE_ROOT")
    if not configured:
        return
    source_root = Path(configured).resolve()
    if (source_root / "dist").is_dir():
        source_dist = source_root / "dist"
        source_manifest = source_root / "interface-manifest.json"
    else:
        source_dist = source_root
        source_manifest = source_root.parent / "interface-manifest.json"
    # Validate the upstream closure independently.  A byte-equal manifest is
    # insufficient if the configured source has an unlisted file, stale
    # digest, open reference, or noncanonical byte sequence.
    verify_distribution(source_dist, source_manifest)
    if source_manifest.read_bytes() != manifest_path.read_bytes():
        raise InterfaceError("coupled SPS interface manifest differs from vendored bytes")
    vendor_files = {
        path.relative_to(distribution)
        for path in distribution.rglob("*")
        if path.is_file() and path.name != "upstream-manifest.json"
    }
    source_files = {
        path.relative_to(source_dist)
        for path in source_dist.rglob("*")
        if path.is_file() and path.name != "upstream-manifest.json"
    }
    if source_files != vendor_files:
        raise InterfaceError("coupled SPS interface file closures differ")
    for relative in sorted(vendor_files):
        if (source_dist / relative).read_bytes() != (distribution / relative).read_bytes():
            raise InterfaceError(f"coupled SPS interface drift: {relative}")


def check_consumers() -> None:
    forbidden = re.compile(
        r"(?m)^(?:QUERY_KINDS|LINT_CLASSES|RECORDS|UNIONS|PUBLIC_REASON_CLASSES_V[12]|"
        r"BLOCKER_SCOPES_V2|CONFIG_REASONS_V[12]|REPORT_FAILURES_V[12])\s*="
    )
    ignored_parts = {".venv", "build", "__pycache__"}
    reference_vendor = (
        HARNESS_ROOT / "contracts" / "vendor" / "sps-reference-rev4"
    )
    paths = sorted(
        path
        for path in HARNESS_ROOT.rglob("*.py")
        if not ignored_parts.intersection(path.relative_to(HARNESS_ROOT).parts)
        and reference_vendor not in path.parents
        and path.resolve() != Path(__file__).resolve()
    )
    violations: list[str] = []
    registry = Registry.from_path(VENDOR_ROOT / "interface-registry.json")
    normative_tables: dict[str, frozenset[str]] = {}
    for name in registry.enums:
        values = frozenset(registry.enum_values(name))
        if len(values) >= 3:
            normative_tables[f"enum {name}"] = values
    for name, record_value in registry.records.items():
        values = frozenset(record_value["canonicalFieldOrder"])
        if len(values) >= 3:
            normative_tables[f"record {name}"] = values
    for name in registry.unions:
        values = frozenset(registry.union_variants(name))
        if len(values) >= 3:
            normative_tables[f"union {name}"] = values
    format_literals = frozenset(registry.value["formatLiterals"].values())

    def literal_strings(node: ast.AST) -> frozenset[str] | None:
        candidate = node
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "frozenset"
            and len(node.args) == 1
            and not node.keywords
        ):
            candidate = node.args[0]
        try:
            value = ast.literal_eval(candidate)
        except (ValueError, TypeError):
            return None
        if isinstance(value, dict):
            rows = tuple(value.values())
        elif isinstance(value, (list, tuple, set, frozenset)):
            rows = tuple(value)
        else:
            return None
        if not rows or not all(isinstance(item, str) for item in rows):
            return None
        return frozenset(rows)

    for path in paths:
        relative = str(path.relative_to(HARNESS_ROOT))
        source = path.read_text(encoding="utf-8")
        if forbidden.search(source):
            violations.append(f"{relative}: forbidden copied-table assignment")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as error:
            raise InterfaceError(f"cannot inspect Python consumer {relative}: {error}") from error
        for node in ast.walk(tree):
            value_node: ast.AST | None = None
            if isinstance(node, ast.Assign):
                value_node = node.value
            elif isinstance(node, ast.AnnAssign):
                value_node = node.value
            if value_node is None:
                continue
            values = literal_strings(value_node)
            if values is None:
                continue
            for table_name, table_values in normative_tables.items():
                if values == table_values:
                    violations.append(
                        f"{relative}:{getattr(node, 'lineno', 0)} copies {table_name}"
                    )
            if len(values) >= 3 and values <= format_literals:
                violations.append(
                    f"{relative}:{getattr(node, 'lineno', 0)} copies SPS format literals"
                )
    if violations:
        raise InterfaceError(
            "copied normative interface tables remain: " + "; ".join(violations)
        )


def load_default_registry() -> Registry:
    manifest, registry = verify_distribution()
    verify_lock(manifest, registry)
    return registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-vendor", action="store_true")
    parser.add_argument("--check-consumers", action="store_true")
    parser.add_argument("--validate", nargs=2, metavar=("ROOT_TYPE", "FILE"))
    parser.add_argument("--expect-semantic-rule")
    arguments = parser.parse_args()
    if not (arguments.verify_vendor or arguments.check_consumers or arguments.validate):
        parser.error("select --verify-vendor, --check-consumers, or --validate")
    try:
        manifest, registry = verify_distribution()
        verify_lock(manifest, registry)
        if arguments.verify_vendor:
            validate_vectors(VENDOR_ROOT, registry)
            verify_coupled_vendor(VENDOR_ROOT, VENDOR_MANIFEST)
            print(
                "verified SPS Rev4.1 interface vendor: "
                f"{manifest['schemaSetId']} bundle={manifest['bundle']['sha256']}"
            )
        if arguments.check_consumers:
            check_consumers()
            print("verified SPS interface consumers: no copied normative tables")
        if arguments.validate:
            root_type, filename = arguments.validate
            value = require_canonical(Path(filename).read_bytes())
            registry.validate_root(value, root_type)
            failures = registry.semantic_failures(value, root_type)
            if arguments.expect_semantic_rule:
                if failures != [arguments.expect_semantic_rule]:
                    raise InterfaceError(
                        f"expected semantic rule {arguments.expect_semantic_rule}, got {failures}"
                    )
                print(f"validated {root_type}: schema-valid; semantic failure {failures[0]}")
            elif failures:
                raise InterfaceError(f"semantic validation failed: {failures}")
            else:
                print(f"validated canonical {root_type}: {filename}")
    except (OSError, InterfaceError, KeyError, TypeError, ValueError) as error:
        print(f"SPS interface validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
