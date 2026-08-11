"""A deliberately small, dependency-free strict YAML reader.

The executable reference accepts one human-authored harness artifact in YAML.
Its wire shape needs only nested mappings, scalar sequences, and JSON-like
scalars, so accepting the rest of YAML would add ambiguity without value.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .errors import SchemaError


_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
_PLAIN = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]*")
_INTEGER = re.compile(r"0|[1-9][0-9]*")


@dataclass(frozen=True)
class _Line:
    number: int
    indent: int
    content: str


def load_strict_block_yaml(raw: bytes, source: str) -> dict[str, Any]:
    """Parse the closed block-YAML subset used by counterexample pairs."""

    if raw.startswith(b"\xef\xbb\xbf"):
        raise SchemaError(f"{source}: UTF-8 BOM is forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SchemaError(f"{source}: invalid UTF-8") from exc
    lines: list[_Line] = []
    for number, physical in enumerate(text.splitlines(), start=1):
        if "\t" in physical:
            raise SchemaError(f"{source}:{number}: tabs are forbidden")
        if physical.rstrip(" ") != physical:
            raise SchemaError(f"{source}:{number}: trailing whitespace is forbidden")
        if not physical:
            continue
        indent = len(physical) - len(physical.lstrip(" "))
        if indent % 2:
            raise SchemaError(f"{source}:{number}: indentation must use two spaces")
        content = physical[indent:]
        if content.startswith(("#", "%", "---", "...")):
            raise SchemaError(f"{source}:{number}: comments and YAML directives are forbidden")
        lines.append(_Line(number, indent, content))
    if not lines:
        raise SchemaError(f"{source}: empty YAML document")
    if lines[0].indent != 0:
        raise SchemaError(f"{source}:{lines[0].number}: top level must be unindented")
    value, cursor = _parse_node(lines, 0, 0, source)
    if cursor != len(lines):
        line = lines[cursor]
        raise SchemaError(f"{source}:{line.number}: unexpected indentation")
    if not isinstance(value, dict):
        raise SchemaError(f"{source}: top-level value must be a mapping")
    return value


def _parse_node(
    lines: list[_Line], cursor: int, indent: int, source: str
) -> tuple[Any, int]:
    line = lines[cursor]
    if line.indent != indent:
        raise SchemaError(f"{source}:{line.number}: unexpected indentation")
    if line.content.startswith("- "):
        return _parse_sequence(lines, cursor, indent, source)
    return _parse_mapping(lines, cursor, indent, source)


def _parse_mapping(
    lines: list[_Line], cursor: int, indent: int, source: str
) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while cursor < len(lines):
        line = lines[cursor]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise SchemaError(f"{source}:{line.number}: unexpected indentation")
        if line.content.startswith("- "):
            break
        if ":" not in line.content:
            raise SchemaError(f"{source}:{line.number}: expected mapping entry")
        key, remainder = line.content.split(":", 1)
        if not _KEY.fullmatch(key) or key == "<<":
            raise SchemaError(f"{source}:{line.number}: invalid mapping key")
        if key in result:
            raise SchemaError(f"{source}:{line.number}: duplicate key {key!r}")
        if remainder:
            if not remainder.startswith(" ") or remainder.startswith("  "):
                raise SchemaError(f"{source}:{line.number}: scalar requires one separating space")
            result[key] = _parse_scalar(remainder[1:], source, line.number)
            cursor += 1
            continue
        cursor += 1
        if cursor >= len(lines):
            raise SchemaError(f"{source}:{line.number}: null/empty values are forbidden")
        if lines[cursor].indent == indent and lines[cursor].content.startswith("- "):
            # PyYAML and the YAML block grammar commonly render a scalar
            # sequence without extra indentation under its mapping key.
            result[key], cursor = _parse_sequence(lines, cursor, indent, source)
            continue
        if lines[cursor].indent <= indent:
            raise SchemaError(f"{source}:{line.number}: null/empty values are forbidden")
        if lines[cursor].indent != indent + 2:
            raise SchemaError(f"{source}:{lines[cursor].number}: nesting must increase by two spaces")
        result[key], cursor = _parse_node(lines, cursor, indent + 2, source)
    return result, cursor


def _parse_sequence(
    lines: list[_Line], cursor: int, indent: int, source: str
) -> tuple[list[Any], int]:
    result: list[Any] = []
    while cursor < len(lines):
        line = lines[cursor]
        if line.indent < indent:
            break
        if line.indent != indent or not line.content.startswith("- "):
            if line.indent == indent:
                break
            raise SchemaError(f"{source}:{line.number}: unexpected sequence indentation")
        scalar = line.content[2:]
        if not scalar:
            raise SchemaError(f"{source}:{line.number}: nested sequence items are forbidden")
        result.append(_parse_scalar(scalar, source, line.number))
        cursor += 1
    return result, cursor


def _parse_scalar(value: str, source: str, number: int) -> str | int | bool | dict[str, Any]:
    # The sole flow-style exception is the unambiguous empty mapping needed by
    # pair partitions with no Low entry inputs.
    if value == "{}":
        return {}
    if not value or value[0] in "&*!{[" or value in {"null", "Null", "NULL", "~"}:
        raise SchemaError(f"{source}:{number}: forbidden YAML scalar")
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SchemaError(f"{source}:{number}: invalid quoted string") from exc
        if not isinstance(decoded, str):
            raise SchemaError(f"{source}:{number}: quoted scalar must be a string")
        return decoded
    if value in {"true", "false"}:
        return value == "true"
    if _INTEGER.fullmatch(value):
        return int(value)
    if _PLAIN.fullmatch(value):
        return value
    raise SchemaError(f"{source}:{number}: scalar is outside the strict YAML subset")
