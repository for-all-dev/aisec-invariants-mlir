"""Strict loaders for the namespaced executable-reference artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import load_json_bytes
from .errors import SchemaError


@dataclass(frozen=True)
class InputDecl:
    input_id: str
    width: int
    classification: str
    host: str


@dataclass(frozen=True)
class Coalition:
    coalition_id: str
    principals: frozenset[str]
    controlled_hosts: frozenset[str]


def load_fixture(path: Path) -> dict[str, Any]:
    try:
        value = load_json_bytes(path.read_bytes())
    except (OSError, SchemaError) as exc:
        raise SchemaError(f"{path}: cannot load fixture: {exc}") from exc
    if not isinstance(value, dict):
        raise SchemaError(f"{path}: fixture must be a JSON object")
    require_exact_keys(
        value,
        {
            "formatId",
            "familyId",
            "caseId",
            "kind",
            "requirementRefs",
            "input",
            "expected",
        },
        f"{path}",
    )
    require_literal(value, "formatId", "SPS-Executable-Reference-Fixture-v3", str(path))
    for key in ("familyId", "caseId", "kind"):
        require_identifier(value.get(key), f"{path}.{key}")
    refs = value["requirementRefs"]
    if not isinstance(refs, list) or not refs or not all(isinstance(x, str) for x in refs):
        raise SchemaError(f"{path}.requirementRefs: expected nonempty string list")
    if not isinstance(value["input"], dict) or not isinstance(value["expected"], dict):
        raise SchemaError(f"{path}: input and expected must be objects")
    return value


def parse_program(value: Any, path: str = "$.input.program") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{path}: program must be an object")
    require_exact_keys(
        value,
        {
            "formatId",
            "entryId",
            "entryHost",
            "observerProfile",
            "inputs",
            "abi",
            "admission",
            "statements",
        },
        path,
    )
    require_literal(value, "formatId", "SPS-Reference-Program-v3", path)
    require_identifier(value["entryId"], f"{path}.entryId")
    require_identifier(value["entryHost"], f"{path}.entryHost")
    if value["observerProfile"] not in {
        "EventInterfaceOnly",
        "ArchitecturalStateSnapshots",
    }:
        raise SchemaError(f"{path}.observerProfile: unsupported observer profile")
    inputs = value["inputs"]
    if not isinstance(inputs, list):
        raise SchemaError(f"{path}.inputs: expected list")
    seen: set[str] = set()
    for index, item in enumerate(inputs):
        item_path = f"{path}.inputs[{index}]"
        require_exact_keys(item, {"id", "width", "classification", "host"}, item_path)
        require_identifier(item["id"], f"{item_path}.id")
        if item["id"] in seen:
            raise SchemaError(f"{item_path}.id: duplicate input")
        seen.add(item["id"])
        require_positive_int(item["width"], f"{item_path}.width")
        if item["width"] > 16:
            raise SchemaError(f"{item_path}.width: reference cap is 16 bits")
        if item["classification"] not in {"Low", "High"}:
            raise SchemaError(f"{item_path}.classification: expected Low or High")
        require_identifier(item["host"], f"{item_path}.host")
    parse_abi(value["abi"], f"{path}.abi")
    validate_expression(value["admission"], f"{path}.admission")
    if not isinstance(value["statements"], list):
        raise SchemaError(f"{path}.statements: expected list")
    validate_statements(value["statements"], f"{path}.statements")
    return value


def parse_abi(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise SchemaError(f"{path}: expected object")
    require_exact_keys(value, {"return", "roots", "terminalOutputOrder"}, path)
    result = value["return"]
    if result is not None:
        if not isinstance(result, dict):
            raise SchemaError(f"{path}.return: expected object or null")
        require_exact_keys(result, {"outputId", "width", "host", "byteOrder"}, f"{path}.return")
        require_identifier(result["outputId"], f"{path}.return.outputId")
        require_positive_int(result["width"], f"{path}.return.width")
        require_identifier(result["host"], f"{path}.return.host")
        if result["byteOrder"] not in {"LittleEndian", "BigEndian"}:
            raise SchemaError(f"{path}.return.byteOrder: invalid byte order")
    roots = value["roots"]
    if not isinstance(roots, list):
        raise SchemaError(f"{path}.roots: expected list")
    seen: set[str] = set()
    terminal_output_ids: list[str] = []
    if result is not None:
        terminal_output_ids.append(result["outputId"])
    for index, root in enumerate(roots):
        root_path = f"{path}.roots[{index}]"
        require_exact_keys(
            root,
            {
                "id",
                "byteLength",
                "host",
                "terminalOutput",
                "outputId",
                "initialBytes",
                "initialized",
            },
            root_path,
        )
        require_identifier(root["id"], f"{root_path}.id")
        if root["id"] in seen:
            raise SchemaError(f"{root_path}.id: duplicate root")
        seen.add(root["id"])
        require_positive_int(root["byteLength"], f"{root_path}.byteLength")
        require_identifier(root["host"], f"{root_path}.host")
        if not isinstance(root["terminalOutput"], bool):
            raise SchemaError(f"{root_path}.terminalOutput: expected Boolean")
        if root["terminalOutput"]:
            require_identifier(root["outputId"], f"{root_path}.outputId")
            terminal_output_ids.append(root["outputId"])
        elif root["outputId"] is not None:
            raise SchemaError(
                f"{root_path}.outputId: internal roots require null outputId"
            )
        raw = root["initialBytes"]
        init = root["initialized"]
        if (
            not isinstance(raw, list)
            or len(raw) != root["byteLength"]
            or not all(
                isinstance(x, int)
                and not isinstance(x, bool)
                and 0 <= x <= 255
                for x in raw
            )
        ):
            raise SchemaError(f"{root_path}.initialBytes: wrong byte vector")
        if (
            not isinstance(init, list)
            or len(init) != root["byteLength"]
            or not all(isinstance(x, bool) for x in init)
        ):
            raise SchemaError(f"{root_path}.initialized: wrong Boolean vector")

    if len(terminal_output_ids) != len(set(terminal_output_ids)):
        raise SchemaError(f"{path}: terminal output IDs must be unique")
    order = value["terminalOutputOrder"]
    if not isinstance(order, list):
        raise SchemaError(f"{path}.terminalOutputOrder: expected list")
    for index, output_id in enumerate(order):
        require_identifier(output_id, f"{path}.terminalOutputOrder[{index}]")
    if len(order) != len(set(order)):
        raise SchemaError(f"{path}.terminalOutputOrder: duplicate output ID")
    if len(order) != len(terminal_output_ids) or set(order) != set(
        terminal_output_ids
    ):
        raise SchemaError(
            f"{path}.terminalOutputOrder: must exactly cover return and terminal roots"
        )


def parse_coalition(value: Any, path: str = "$.input.coalition") -> Coalition:
    if not isinstance(value, dict):
        raise SchemaError(f"{path}: expected object")
    require_exact_keys(value, {"id", "principals", "controlledHosts"}, path)
    require_identifier(value["id"], f"{path}.id")
    for key in ("principals", "controlledHosts"):
        if not isinstance(value[key], list) or not all(
            isinstance(item, str) for item in value[key]
        ):
            raise SchemaError(f"{path}.{key}: expected string list")
        if len(value[key]) != len(set(value[key])):
            raise SchemaError(f"{path}.{key}: duplicate member")
        for index, member in enumerate(value[key]):
            require_identifier(member, f"{path}.{key}[{index}]")
    return Coalition(
        value["id"], frozenset(value["principals"]), frozenset(value["controlledHosts"])
    )


def validate_statements(statements: list[Any], path: str) -> None:
    seen_sites: set[str] = set()

    def visit(items: list[Any], item_path: str) -> None:
        for index, statement in enumerate(items):
            current = f"{item_path}[{index}]"
            if not isinstance(statement, dict):
                raise SchemaError(f"{current}: statement must be an object")
            op = statement.get("op")
            site = statement.get("site")
            require_identifier(op, f"{current}.op")
            require_identifier(site, f"{current}.site")
            if site in seen_sites:
                raise SchemaError(f"{current}.site: duplicate stable site")
            seen_sites.add(site)
            allowed: dict[str, set[str]] = {
                "set": {"op", "site", "target", "value"},
                "store": {"op", "site", "root", "offset", "value", "byteOrder"},
                "if": {
                    "op",
                    "site",
                    "condition",
                    "thenSuccessor",
                    "elseSuccessor",
                    "then",
                    "else",
                },
                "loop": {"op", "site", "boundId", "boundMaximum", "iterations", "body"},
                "releaseAttempt": {
                    "op",
                    "site",
                    "releaseId",
                    "guard",
                    "value",
                    "audience",
                    "host",
                    "footprintBytes",
                },
                "transfer": {
                    "op",
                    "site",
                    "value",
                    "sourceHost",
                    "destinationHosts",
                },
                "return": {"op", "site", "value"},
            }
            if op not in allowed:
                raise SchemaError(f"{current}.op: unsupported reference operation {op!r}")
            require_exact_keys(statement, allowed[op], current)
            if op == "set":
                require_identifier(statement["target"], f"{current}.target")
                validate_expression(statement["value"], f"{current}.value")
            elif op == "store":
                require_identifier(statement["root"], f"{current}.root")
                require_natural_int(statement["offset"], f"{current}.offset")
                if statement["byteOrder"] not in {"LittleEndian", "BigEndian"}:
                    raise SchemaError(f"{current}.byteOrder: invalid byte order")
                validate_expression(statement["value"], f"{current}.value")
            elif op == "if":
                validate_expression(statement["condition"], f"{current}.condition")
                require_identifier(
                    statement["thenSuccessor"], f"{current}.thenSuccessor"
                )
                require_identifier(
                    statement["elseSuccessor"], f"{current}.elseSuccessor"
                )
                if not isinstance(statement["then"], list) or not isinstance(
                    statement["else"], list
                ):
                    raise SchemaError(f"{current}: branch arms must be lists")
                visit(statement["then"], f"{current}.then")
                visit(statement["else"], f"{current}.else")
            elif op == "loop":
                require_identifier(statement["boundId"], f"{current}.boundId")
                require_natural_int(
                    statement["boundMaximum"], f"{current}.boundMaximum"
                )
                validate_expression(
                    statement["iterations"], f"{current}.iterations"
                )
                if not isinstance(statement["body"], list):
                    raise SchemaError(f"{current}.body: expected list")
                visit(statement["body"], f"{current}.body")
            elif op == "releaseAttempt":
                require_identifier(statement["releaseId"], f"{current}.releaseId")
                require_identifier(statement["host"], f"{current}.host")
                validate_expression(statement["guard"], f"{current}.guard")
                validate_expression(statement["value"], f"{current}.value")
                audience = statement["audience"]
                if not isinstance(audience, list):
                    raise SchemaError(f"{current}.audience: expected unique ID list")
                for audience_index, principal in enumerate(audience):
                    require_identifier(
                        principal, f"{current}.audience[{audience_index}]"
                    )
                if len(audience) != len(set(audience)):
                    raise SchemaError(f"{current}.audience: expected unique ID list")
                footprint = statement["footprintBytes"]
                if not isinstance(footprint, list) or not footprint:
                    raise SchemaError(
                        f"{current}.footprintBytes: expected nonempty natural list"
                    )
                for footprint_index, byte_index in enumerate(footprint):
                    require_natural_int(
                        byte_index,
                        f"{current}.footprintBytes[{footprint_index}]",
                    )
                if footprint != sorted(set(footprint)):
                    raise SchemaError(
                        f"{current}.footprintBytes: expected sorted unique list"
                    )
            elif op == "transfer":
                require_identifier(
                    statement["sourceHost"], f"{current}.sourceHost"
                )
                validate_expression(statement["value"], f"{current}.value")
                destinations = statement["destinationHosts"]
                if not isinstance(destinations, list) or not destinations:
                    raise SchemaError(
                        f"{current}.destinationHosts: expected nonempty unique ID list"
                    )
                for destination_index, host in enumerate(destinations):
                    require_identifier(
                        host, f"{current}.destinationHosts[{destination_index}]"
                    )
                if len(destinations) != len(set(destinations)):
                    raise SchemaError(
                        f"{current}.destinationHosts: expected nonempty unique ID list"
                    )
            elif op == "return" and statement["value"] is not None:
                validate_expression(statement["value"], f"{current}.value")

    visit(statements, path)


def require_exact_keys(value: Any, expected: set[str], path: str) -> None:
    if not isinstance(value, dict):
        raise SchemaError(f"{path}: expected object")
    actual = set(value)
    if actual != expected:
        raise SchemaError(
            f"{path}: field mismatch; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def require_literal(value: dict[str, Any], key: str, literal: Any, path: str) -> None:
    if value.get(key) != literal:
        raise SchemaError(f"{path}.{key}: expected {literal!r}")


def require_identifier(value: Any, path: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-" for ch in value)
    ):
        raise SchemaError(f"{path}: invalid stable identifier")


def require_positive_int(value: Any, path: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise SchemaError(f"{path}: expected positive integer")


def require_natural_int(value: Any, path: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SchemaError(f"{path}: expected natural")


def validate_expression(value: Any, path: str) -> None:
    if not isinstance(value, dict) or len(value) != 1:
        raise SchemaError(f"{path}: expression must have one constructor")
    op, payload = next(iter(value.items()))
    if op == "var":
        require_identifier(payload, f"{path}.var")
        return
    if op == "const":
        require_exact_keys(payload, {"width", "value"}, f"{path}.const")
        require_positive_int(payload["width"], f"{path}.const.width")
        require_natural_int(payload["value"], f"{path}.const.value")
        if payload["value"] >= 1 << payload["width"]:
            raise SchemaError(f"{path}.const.value: does not fit width")
        return
    if op == "bool":
        if not isinstance(payload, bool):
            raise SchemaError(f"{path}.bool: expected Boolean")
        return
    if op == "not":
        validate_expression(payload, f"{path}.not")
        return
    if op in {"eq", "ult", "add", "xor", "and", "or"}:
        if not isinstance(payload, list) or len(payload) != 2:
            raise SchemaError(f"{path}.{op}: expected two operands")
        validate_expression(payload[0], f"{path}.{op}[0]")
        validate_expression(payload[1], f"{path}.{op}[1]")
        return
    if op == "extract":
        require_exact_keys(payload, {"value", "low", "width"}, f"{path}.extract")
        require_natural_int(payload["low"], f"{path}.extract.low")
        require_positive_int(payload["width"], f"{path}.extract.width")
        validate_expression(payload["value"], f"{path}.extract.value")
        return
    if op == "load":
        require_exact_keys(
            payload, {"root", "offset", "width", "byteOrder"}, f"{path}.load"
        )
        require_identifier(payload["root"], f"{path}.load.root")
        require_natural_int(payload["offset"], f"{path}.load.offset")
        require_positive_int(payload["width"], f"{path}.load.width")
        if payload["width"] % 8 != 0:
            raise SchemaError(f"{path}.load.width: reference loads must be byte-aligned")
        if payload["byteOrder"] not in {"LittleEndian", "BigEndian"}:
            raise SchemaError(f"{path}.load.byteOrder: invalid byte order")
        return
    raise SchemaError(f"{path}: unsupported expression constructor {op!r}")
