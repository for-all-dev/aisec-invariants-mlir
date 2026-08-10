"""Canonical JSON helpers for reference-only artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .errors import SchemaError


def _reject_noncanonical_numbers(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        raise SchemaError(f"{path}: floating-point JSON numbers are forbidden")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise SchemaError(f"{path}: JSON object keys must be strings")
            _reject_noncanonical_numbers(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_noncanonical_numbers(child, f"{path}[{index}]")


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for a reference artifact."""

    _reject_noncanonical_numbers(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json_bytes(raw: bytes) -> Any:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SchemaError(f"duplicate JSON object key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaError(f"invalid UTF-8 JSON: {exc}") from exc
    _reject_noncanonical_numbers(value)
    return value
