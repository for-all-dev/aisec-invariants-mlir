"""Small closed-world JSON Schema evaluator for SPS authoring documents.

The vendored schemas intentionally use a narrow Draft 2020-12 subset.  Keeping
that subset here avoids adding a second YAML/JSON stack to the test harness.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class SchemaError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SchemaError(f"duplicate schema field {key!r}")
        result[key] = value
    return result


def load_schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except OSError as error:
        raise SchemaError(f"cannot read schema {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SchemaError(f"invalid schema JSON {path}: {error.msg}") from error
    if not isinstance(value, dict):
        raise SchemaError(f"schema {path} must contain an object")
    return value


def _same(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    raise SchemaError(f"vendored schema uses unsupported type {expected!r}")


def _resolve_ref(root: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise SchemaError(f"only local schema references are supported: {reference!r}")
    value: Any = root
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, Mapping) or part not in value:
            raise SchemaError(f"unresolved schema reference {reference!r}")
        value = value[part]
    if not isinstance(value, Mapping):
        raise SchemaError(f"schema reference is not an object: {reference!r}")
    return value


def _validate(value: Any, schema: Mapping[str, Any], root: Mapping[str, Any], where: str) -> None:
    if "$ref" in schema:
        _validate(value, _resolve_ref(root, schema["$ref"]), root, where)
        return

    if "oneOf" in schema:
        choices = schema["oneOf"]
        if not isinstance(choices, list):
            raise SchemaError("oneOf must be an array in the vendored schema")
        failures: list[str] = []
        matches = 0
        for choice in choices:
            try:
                _validate(value, choice, root, where)
            except SchemaError as error:
                failures.append(str(error))
            else:
                matches += 1
        if matches != 1:
            detail = failures[0] if failures else "multiple alternatives matched"
            raise SchemaError(f"{where}: expected exactly one schema alternative ({detail})")
        return

    if "const" in schema and not _same(value, schema["const"]):
        raise SchemaError(f"{where}: expected the literal {schema['const']!r}")
    if "enum" in schema and not any(_same(value, item) for item in schema["enum"]):
        raise SchemaError(f"{where}: value is not one of {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        raise SchemaError(f"{where}: expected {expected_type}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise SchemaError(f"{where}: string is too short")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise SchemaError(f"{where}: string does not match {schema['pattern']!r}")

    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError(f"{where}: integer must be at least {schema['minimum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise SchemaError(f"{where}: array has fewer than {schema['minItems']} items")
        if schema.get("uniqueItems"):
            keys = [_json_key(item) for item in value]
            if len(keys) != len(set(keys)):
                raise SchemaError(f"{where}: array items must be unique")
        if "items" in schema:
            for index, item in enumerate(value):
                _validate(item, schema["items"], root, f"{where}[{index}]")

    if isinstance(value, Mapping):
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            raise SchemaError(
                f"{where}: object has fewer than {schema['minProperties']} properties"
            )
        required = schema.get("required", [])
        missing = [field for field in required if field not in value]
        if missing:
            raise SchemaError(f"{where}: missing required fields {missing!r}")
        if "propertyNames" in schema:
            for key in value:
                _validate(key, schema["propertyNames"], root, f"{where} key {key!r}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], root, f"{where}.{key}")
            elif additional is False:
                raise SchemaError(f"{where}: unknown field {key!r}")
            elif isinstance(additional, Mapping):
                _validate(item, additional, root, f"{where}.{key}")


def validate(value: Any, schema: Mapping[str, Any], *, source: str) -> None:
    _validate(value, schema, schema, source)
