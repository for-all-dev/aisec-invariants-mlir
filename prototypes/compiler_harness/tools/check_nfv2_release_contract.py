#!/usr/bin/env python3
"""Validate the executable harness contract for an NFv2 release carrier.

This is deliberately a structural preflight checker.  It lets stock LLVM test
the Rev4.1 interface contract without pretending that the patched intrinsic,
normalizer, relational verifier, or replay engine exists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


FORMAT_ID = "SPS-Harness-NFv2-Release-Carrier-Cases-v2"
PROFILE_ID = "SPS-LLVM-NF-v2"
INTRINSIC = "llvm.sps.release"
IDENTITY_AUTHORITY = (
    "ReleaseImplementationBindingV2.emitMarkerInstructionId"
)
INTEGER_TYPE = re.compile(r"i[1-9][0-9]*\Z")
INTEGER_CONSTANT = re.compile(r"(?:-?[0-9]+|0x[0-9A-Fa-f]+)\Z")
FUNCTION_START = re.compile(
    r"^\s*define\b.*@(?P<name>[-A-Za-z$._0-9]+)\([^)]*\).*\{\s*$"
)
LABEL = re.compile(r"^\s*(?P<name>[-A-Za-z$._0-9]+):(?:\s*;.*)?$")
INTRINSIC_CALL = re.compile(
    r"\bcall\s+(?P<result>[^\s]+)\s+"
    r"(?P<variadic>\(\.\.\.\)\s+)?"
    r"@llvm\.sps\.release\((?P<arguments>.*)\)"
)


class ContractError(ValueError):
    """A malformed harness contract input."""


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _load_cases(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw, object_pairs_hook=_object_without_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError, ContractError) as error:
        raise ContractError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError("case catalog must be a JSON object")
    required = {
        "formatId": FORMAT_ID,
        "profileId": PROFILE_ID,
        "intrinsic": INTRINSIC,
        "identityAuthority": IDENTITY_AUTHORITY,
    }
    for field, expected in required.items():
        if value.get(field) != expected:
            raise ContractError(f"{field} must be {expected!r}")
    if set(value) != {*required, "module", "cases"}:
        raise ContractError("case catalog has missing or unknown top-level members")
    if not isinstance(value["module"], str) or not value["module"]:
        raise ContractError("module must be a nonempty relative path")
    cases = value["cases"]
    if not isinstance(cases, list) or not cases:
        raise ContractError("cases must be a nonempty array")
    return value


def _extract_functions(text: str) -> dict[str, list[tuple[str, str]]]:
    functions: dict[str, list[tuple[str, str]]] = {}
    current_name: str | None = None
    current_block = "entry"
    ordinal = 0
    for source_line in text.splitlines():
        if current_name is None:
            match = FUNCTION_START.match(source_line)
            if match:
                current_name = match.group("name")
                if current_name in functions:
                    raise ContractError(f"duplicate function: {current_name}")
                functions[current_name] = []
                current_block = "entry"
                ordinal = 0
            continue
        if source_line.strip() == "}":
            current_name = None
            continue
        label = LABEL.match(source_line)
        if label:
            current_block = label.group("name")
            ordinal = 0
            continue
        stripped = source_line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        instruction_id = f"{current_name}:{current_block}:{ordinal}"
        functions[current_name].append((instruction_id, stripped))
        ordinal += 1
    if current_name is not None:
        raise ContractError(f"unterminated function: {current_name}")
    return functions


def _mismatch(reason: str) -> dict[str, str]:
    return {"tag": "ReleaseCarrierMismatch", "reason": reason}


def _missing_carrier_reason(body: list[tuple[str, str]]) -> str:
    text = "\n".join(line for _, line in body)
    if "asm sideeffect" in text:
        return "LegacyInlineAsmCarrier"
    if "@__sps_invalid_callable_emit_" in text:
        return "LegacyFunctionCarrier"
    if re.search(r"\bcall\b.*@(release_wrapper|sps_release_invalid_callable)\b", text):
        return "LegacyOutlinedWrapperCarrier"
    if "!sps.release" in text:
        return "MetadataOnlyCarrier"
    if any(re.search(r"\bstore\b", line) for _, line in body):
        return "StoreOnlyCarrier"
    return "MissingReleaseCarrier"


def _argument_types(arguments: str) -> tuple[list[str], list[str]]:
    if not arguments.strip():
        return [], []
    pieces = [piece.strip() for piece in arguments.split(",")]
    types: list[str] = []
    values: list[str] = []
    for piece in pieces:
        fields = piece.split(maxsplit=1)
        if len(fields) != 2:
            raise ContractError(f"malformed intrinsic operand: {piece!r}")
        types.append(fields[0])
        values.append(fields[1])
    return types, values


def _check_case(
    case: dict[str, Any], functions: dict[str, list[tuple[str, str]]]
) -> dict[str, Any]:
    required = {
        "id",
        "function",
        "releaseId",
        "flattenedReleaseTypeLeaves",
        "bindings",
        "semanticEquivalence",
        "expected",
    }
    if set(case) != required:
        raise ContractError(
            f"case {case.get('id', '<missing>')}: missing or unknown members"
        )
    case_id = case["id"]
    function = case["function"]
    release_id = case["releaseId"]
    leaves = case["flattenedReleaseTypeLeaves"]
    bindings = case["bindings"]
    semantic_equivalence = case["semanticEquivalence"]
    if not all(isinstance(value, str) and value for value in (case_id, function, release_id)):
        raise ContractError("case id, function, and releaseId must be nonempty strings")
    if function not in functions:
        raise ContractError(f"case {case_id}: unknown function {function!r}")
    if (
        not isinstance(leaves, list)
        or any(not isinstance(leaf, str) or not INTEGER_TYPE.fullmatch(leaf) for leaf in leaves)
    ):
        raise ContractError(f"case {case_id}: release leaves must be integer types")
    if not isinstance(bindings, list):
        raise ContractError(f"case {case_id}: bindings must be an array")
    if semantic_equivalence not in {"established", "unresolved"}:
        raise ContractError(f"case {case_id}: invalid semanticEquivalence")

    body = functions[function]
    markers = [
        (instruction_id, line)
        for instruction_id, line in body
        if INTRINSIC in line and re.search(r"\bcall\b", line)
    ]
    if not markers:
        return _mismatch(_missing_carrier_reason(body))
    if len(markers) != 1:
        return _mismatch("DuplicateReleaseCarrier")

    marker_id, marker_line = markers[0]
    call = INTRINSIC_CALL.search(marker_line)
    if not call:
        return _mismatch("MalformedIntrinsicCall")
    if call.group("result") != "void":
        return _mismatch("NonVoidIntrinsicResult")
    if call.group("variadic") is None:
        return _mismatch("NonVariadicIntrinsicCall")
    try:
        operand_types, operand_values = _argument_types(call.group("arguments"))
    except ContractError:
        return _mismatch("MalformedIntrinsicOperand")
    if any(not INTEGER_TYPE.fullmatch(operand_type) for operand_type in operand_types):
        return _mismatch("NonIntegerPayloadLeaf")
    if (
        len(operand_types) == len(leaves) + 1
        and operand_types[1:] == leaves
        and INTEGER_CONSTANT.fullmatch(operand_values[0])
    ):
        return _mismatch("ReleaseIdOperandForbidden")
    if len(operand_types) != len(leaves):
        return _mismatch("PayloadArityMismatch")
    if operand_types != leaves:
        if sorted(operand_types) == sorted(leaves):
            return _mismatch("PayloadOrderMismatch")
        return _mismatch("PayloadWidthMismatch")

    if not bindings:
        return _mismatch("MissingInstructionBinding")
    if len(bindings) != 1:
        return _mismatch("AmbiguousInstructionBinding")
    binding = bindings[0]
    if not isinstance(binding, dict) or set(binding) != {
        "releaseId",
        "emitMarkerInstructionId",
    }:
        raise ContractError(f"case {case_id}: malformed binding")
    if binding["releaseId"] != release_id:
        return _mismatch("WrongReleaseBinding")
    if binding["emitMarkerInstructionId"] != marker_id:
        return _mismatch("StaleInstructionBinding")
    if semantic_equivalence == "unresolved":
        return {
            "tag": "ReleaseConformanceUnknown",
            "reason": "UnresolvedReleaseEquivalence",
        }
    return {"tag": "AcceptedPreflight"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    arguments = parser.parse_args()
    try:
        catalog = _load_cases(arguments.catalog)
        module_path = (arguments.catalog.parent / catalog["module"]).resolve()
        module_path.relative_to(arguments.catalog.parent.resolve())
        module_text = module_path.read_text(encoding="utf-8")
        functions = _extract_functions(module_text)
        seen: set[str] = set()
        for raw_case in catalog["cases"]:
            if not isinstance(raw_case, dict):
                raise ContractError("every case must be an object")
            case_id = raw_case.get("id")
            if case_id in seen:
                raise ContractError(f"duplicate case id: {case_id}")
            seen.add(case_id)
            actual = _check_case(raw_case, functions)
            expected = raw_case["expected"]
            if actual != expected:
                raise ContractError(
                    f"case {case_id}: expected {expected!r}, got {actual!r}"
                )
            if actual["tag"] == "AcceptedPreflight":
                rendered = actual["tag"]
            else:
                rendered = f"{actual['tag']}({actual['reason']})"
            print(f"{case_id}: {rendered}")
        print(
            f"verified {len(seen)} NFv2 release-carrier contract cases; "
            "claimable=false; ModelStatus=not-computed"
        )
        return 0
    except (ContractError, OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
