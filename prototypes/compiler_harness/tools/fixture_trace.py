#!/usr/bin/env python3
"""Build an expectation-blind fixture-verification trace from typed fragments.

This module deliberately has no snapshot input.  Producers report observations
and decision evidence as strict-YAML fragments; assembly checks their closed
wire shapes, binds them to one session/case/entry, and emits a deterministic
``SPS-Harness-Verification-Trace``.  Comparing that trace with fixture
expectations is a separate verifier phase.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from yaml.tokens import AliasToken, AnchorToken, TagToken

import checkpoint_model
import sps_interfaces


FRAGMENT_FORMAT = "SPS-Harness-Trace-Fragment"
TRACE_FORMAT = "SPS-Harness-Verification-Trace"
TRACE_AUTHORITY = "TestOnly"

SENSITIVITIES = frozenset({"SyntheticTestData", "Restricted"})
CAPTURE_STATES = frozenset(
    {"Captured", "ProducerFailed", "ExtractionFailed", "Unsupported", "Blocked"}
)
_SPS_REGISTRY = sps_interfaces.load_default_registry()
BLOCKER_SCOPES = frozenset(_SPS_REGISTRY.enum_values("BlockerScopeV2"))
POLICY_STATES = frozenset(
    _SPS_REGISTRY.union_variants("PolicyReviewStatusV2")
)

_CASE_ID = re.compile(r"[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)+\Z")
_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_STABLE_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]*\Z")
_FACT_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CANONICAL_INTEGER = re.compile(r"(?:0|[1-9][0-9]*|-[1-9][0-9]*)\Z")
_DECIMAL_INTEGER_SHAPE = re.compile(r"[+-]?[0-9][0-9_]*\Z")
_DECIMAL_NUMERIC_SHAPE = re.compile(
    r"[+-]?(?=[0-9.])(?=[0-9._eE+-]*[0-9])[0-9._eE+-]+\Z"
)
_BASE_PREFIXED_NUMERIC_SHAPE = re.compile(r"[+-]?0[xXoObB].*\Z")
_SEXAGESIMAL_NUMERIC_SHAPE = re.compile(
    r"[+-]?[0-9][0-9_]*(?::[0-9][0-9_]*)(?:\.[0-9_]*)?\Z"
)
_SPECIAL_FLOAT_SHAPE = re.compile(
    r"[+-]?\.(?:inf|Inf|INF|nan|NaN|NAN)\Z"
)

_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1

_MAX_FRAGMENT_BYTES = 4 * 1024 * 1024
_MAX_FRAGMENTS = 4096
_MAX_YAML_DEPTH = 64
_MAX_YAML_NODES = 100_000

# These fields would let a producer copy, predict, or pre-compare the authored
# expectation.  Normalization removes punctuation so spelling variants such as
# ``expected_result`` and ``expected-result`` cannot bypass the boundary.
_FORBIDDEN_PREFIXES = frozenset(
    {
        "because",
        "comparison",
        "expect",
        "match",
        "mismatch",
        "modelstatus",
        "outcome",
        "position",
        "snapshot",
        "spsmodelstatus",
        "testoutcome",
    }
)


class TraceError(checkpoint_model.CheckpointError):
    """A trace fragment or assembled trace violates the harness contract."""


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


class _TraceYamlLoader(yaml.BaseLoader):
    """Loader for the trace wire's deliberately small scalar language."""


def _strict_plain_scalar(value: str, mark: yaml.Mark) -> str | bool | int:
    if value == "" or value in {"null", "Null", "NULL", "~"}:
        raise yaml.constructor.ConstructorError(
            None, None, "YAML null values are forbidden", mark
        )
    if value == "true":
        return True
    if value == "false":
        return False
    if _CANONICAL_INTEGER.fullmatch(value):
        integer = int(value, 10)
        if _INT64_MIN <= integer <= _INT64_MAX:
            return integer
        raise yaml.constructor.ConstructorError(
            None, None, "integer scalar is outside signed int64 range", mark
        )
    if (
        _DECIMAL_INTEGER_SHAPE.fullmatch(value)
        or _DECIMAL_NUMERIC_SHAPE.fullmatch(value)
        or _BASE_PREFIXED_NUMERIC_SHAPE.fullmatch(value)
        or _SEXAGESIMAL_NUMERIC_SHAPE.fullmatch(value)
        or _SPECIAL_FLOAT_SHAPE.fullmatch(value)
    ):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "floating-point and non-canonical numeric scalars are forbidden",
            mark,
        )
    return value


def _construct_trace_scalar(
    loader: _TraceYamlLoader, node: yaml.ScalarNode
) -> str | bool | int:
    del loader
    if node.style is None:
        return _strict_plain_scalar(node.value, node.start_mark)
    return node.value


def _construct_trace_mapping(
    loader: _TraceYamlLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        if not isinstance(key_node, yaml.ScalarNode):
            raise yaml.constructor.ConstructorError(
                None, None, "mapping keys must be scalar strings", key_node.start_mark
            )
        key = key_node.value
        if key == "<<":
            raise yaml.constructor.ConstructorError(
                None, None, "merge keys are not allowed", key_node.start_mark
            )
        if key in result:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_TraceYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG, _construct_trace_scalar
)
_TraceYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_trace_mapping
)


def _require_yaml_event_limits(text: str, *, source: str) -> None:
    """Enforce the C reader's depth/node limits before recursive construction."""

    # Each stack row is [kind, node_depth, mapping_expects_key]. Mapping keys
    # are strings rather than value nodes in the C representation, so they do
    # not consume the node budget or advance the value depth.
    stack: list[list[Any]] = []
    node_count = 0
    for event in yaml.parse(text, Loader=yaml.BaseLoader):
        is_scalar = isinstance(event, yaml.events.ScalarEvent)
        is_sequence = isinstance(event, yaml.events.SequenceStartEvent)
        is_mapping = isinstance(event, yaml.events.MappingStartEvent)
        if not (is_scalar or is_sequence or is_mapping):
            if isinstance(event, yaml.events.SequenceEndEvent):
                if stack and stack[-1][0] == "sequence":
                    stack.pop()
            elif isinstance(event, yaml.events.MappingEndEvent):
                if stack and stack[-1][0] == "mapping":
                    stack.pop()
            continue

        if stack and stack[-1][0] == "mapping" and stack[-1][2]:
            if not is_scalar:
                raise TraceError(f"{source}: mapping keys must be scalar strings")
            stack[-1][2] = False
            continue

        depth = stack[-1][1] + 1 if stack else 0
        if depth > _MAX_YAML_DEPTH:
            raise TraceError(f"{source}: YAML nesting limit exceeded")
        node_count += 1
        if node_count > _MAX_YAML_NODES:
            raise TraceError(f"{source}: YAML node limit exceeded")

        if stack and stack[-1][0] == "mapping":
            stack[-1][2] = True
        if is_sequence:
            stack.append(["sequence", depth, False])
        elif is_mapping:
            stack.append(["mapping", depth, True])


def _strict_yaml_load(raw: bytes, *, source: str) -> dict[str, Any]:
    """Decode the same closed YAML scalar subset consumed by the C verifier."""

    if len(raw) > _MAX_FRAGMENT_BYTES:
        raise TraceError(f"{source}: input exceeds 4 MiB limit")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise TraceError(f"{source}: UTF-8 BOM is forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TraceError(f"{source}: invalid UTF-8") from error
    try:
        for token in yaml.scan(text):
            if isinstance(token, (AliasToken, AnchorToken, TagToken)):
                raise TraceError(
                    f"{source}: aliases, anchors, and explicit tags are forbidden"
                )
        _require_yaml_event_limits(text, source=source)
        value = yaml.load(text, Loader=_TraceYamlLoader)
    except TraceError:
        raise
    except RecursionError as error:
        raise TraceError(f"{source}: YAML nesting limit exceeded") from error
    except (yaml.YAMLError, UnicodeError, ValueError) as error:
        raise TraceError(f"{source}: invalid strict YAML: {error}") from error
    _require_strict_value(value, source)
    if not isinstance(value, dict):
        raise TraceError(f"{source}: top-level value must be a mapping")
    return value


def _exact_fields(
    value: Mapping[str, Any], required: set[str], optional: set[str], where: str
) -> None:
    actual = set(value)
    allowed = required | optional
    if not required <= actual or not actual <= allowed:
        raise TraceError(
            f"{where}: wrong fields; missing={sorted(required - actual)}, "
            f"extra={sorted(actual - allowed)}"
        )


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TraceError(f"{where}: expected mapping")
    return value


def _nonempty_string(
    value: Any, where: str, *, max_length: int | None = None
) -> str:
    if not isinstance(value, str) or value == "":
        raise TraceError(f"{where}: expected nonempty string")
    if max_length is not None and len(value) > max_length:
        raise TraceError(f"{where}: exceeds maximum length {max_length}")
    return value


def _pattern_string(
    value: Any,
    pattern: re.Pattern[str],
    where: str,
    *,
    max_length: int | None = None,
) -> str:
    text = _nonempty_string(value, where, max_length=max_length)
    if pattern.fullmatch(text) is None:
        raise TraceError(f"{where}: invalid value {text!r}")
    return text


def _enum(value: Any, allowed: frozenset[str], where: str) -> str:
    text = _nonempty_string(value, where)
    if text not in allowed:
        raise TraceError(f"{where}: expected one of {sorted(allowed)}, got {text!r}")
    return text


def _boolean(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise TraceError(f"{where}: expected boolean")
    return value


def _sha256(value: Any, where: str) -> str:
    return _pattern_string(value, _SHA256, where)


def _string_list(
    value: Any,
    where: str,
    *,
    nonempty: bool = False,
    item_max_length: int | None = None,
) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "nonempty " if nonempty else ""
        raise TraceError(f"{where}: expected {qualifier}list")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(
            _nonempty_string(
                item, f"{where}[{index}]", max_length=item_max_length
            )
        )
    if len(result) != len(set(result)):
        raise TraceError(f"{where}: duplicate values are forbidden")
    return result


def _normalized_key(key: str) -> str:
    return "".join(
        character.lower()
        for character in key
        if character.isascii() and character.isalnum()
    )


def _require_strict_value(value: Any, where: str = "$") -> tuple[int, int]:
    """Apply the strict YAML/JSON scalar boundary to in-memory callers too."""

    pending: list[tuple[Any, str, int]] = [(value, where, 0)]
    node_count = 0
    text_bytes = 0
    while pending:
        current, current_where, depth = pending.pop()
        if depth > _MAX_YAML_DEPTH:
            raise TraceError(f"{current_where}: YAML nesting limit exceeded")
        node_count += 1
        if node_count > _MAX_YAML_NODES:
            raise TraceError(f"{current_where}: YAML node limit exceeded")
        if current is None or isinstance(current, float):
            raise TraceError(
                f"{current_where}: null and floating-point scalars are forbidden"
            )
        if isinstance(current, str):
            if "\0" in current:
                raise TraceError(f"{current_where}: embedded NUL is forbidden")
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                raise TraceError(
                    f"{current_where}: Unicode surrogate code points are forbidden"
                )
            text_bytes += len(current.encode("utf-8"))
            if text_bytes > _MAX_FRAGMENT_BYTES:
                raise TraceError(
                    f"{current_where}: input exceeds 4 MiB limit"
                )
            continue
        if isinstance(current, bool):
            continue
        if isinstance(current, int):
            if not _INT64_MIN <= current <= _INT64_MAX:
                raise TraceError(
                    f"{current_where}: integer is outside signed int64 range"
                )
            continue
        if isinstance(current, list):
            pending.extend(
                (item, f"{current_where}[{index}]", depth + 1)
                for index, item in enumerate(current)
            )
            continue
        if isinstance(current, Mapping):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise TraceError(f"{current_where}: mapping keys must be strings")
                if "\0" in key:
                    raise TraceError(
                        f"{current_where}: embedded NUL in mapping key is forbidden"
                    )
                if any(0xD800 <= ord(character) <= 0xDFFF for character in key):
                    raise TraceError(
                        f"{current_where}: Unicode surrogate code points in mapping "
                        "keys are forbidden"
                    )
                text_bytes += len(key.encode("utf-8"))
                if text_bytes > _MAX_FRAGMENT_BYTES:
                    raise TraceError(
                        f"{current_where}: input exceeds 4 MiB limit"
                    )
                pending.append((item, f"{current_where}.{key}", depth + 1))
            continue
        raise TraceError(
            f"{current_where}: unsupported value type {type(current).__name__}"
        )
    return node_count, text_bytes


def _canonical_value(value: Any) -> Any:
    """Copy a strict value while canonicalizing every mapping's key order."""

    if isinstance(value, Mapping):
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    return value


def _reject_expectation_fields(value: Any, where: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = _normalized_key(str(key))
            if any(
                normalized.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES
            ):
                raise TraceError(
                    f"{where}: forbidden expectation or snapshot field {key!r}"
                )
            _reject_expectation_fields(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_expectation_fields(item, f"{where}[{index}]")


def _event(value: Any, where: str) -> dict[str, Any]:
    event = _mapping(value, where)
    _exact_fields(event, {"kind", "field"}, {"id"}, where)
    kind = _nonempty_string(event["kind"], f"{where}.kind")
    field = _nonempty_string(event["field"], f"{where}.field")
    if kind not in checkpoint_model.EVENT_FIELDS:
        raise TraceError(f"{where}.kind: unknown SPS event kind {kind!r}")
    if field not in checkpoint_model.EVENT_FIELDS[kind]:
        raise TraceError(
            f"{where}.field: {field!r} is not a modeled field of {kind!r}"
        )
    result: dict[str, Any] = {"kind": kind, "field": field}
    if "id" in event:
        result["id"] = _pattern_string(
            event["id"], _STABLE_ID, f"{where}.id", max_length=256
        )
    return result


def _event_list(value: Any, where: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TraceError(f"{where}: expected list")
    result = [_event(item, f"{where}[{index}]") for index, item in enumerate(value)]
    keys = [checkpoint_model.canonical_bytes(item) for item in result]
    if len(keys) != len(set(keys)):
        raise TraceError(f"{where}: duplicate event selectors are forbidden")
    result.sort(key=checkpoint_model.canonical_bytes)
    return result


def _pipeline_kind(value: Any, where: str) -> str:
    return _enum(value, checkpoint_model.PIPELINE_KINDS, where)


def _capture(value: Any, where: str) -> dict[str, Any]:
    capture = _mapping(value, where)
    state = _enum(capture.get("state"), CAPTURE_STATES, f"{where}.state")
    if state == "Captured":
        _exact_fields(
            capture,
            {"state", "kind", "extractor", "endpoint_sha256", "facts"},
            set(),
            where,
        )
        facts = _mapping(capture["facts"], f"{where}.facts")
        for key in facts:
            _pattern_string(
                key, _FACT_KEY, f"{where}.facts key", max_length=256
            )
        return {
            "state": state,
            "kind": _pipeline_kind(capture["kind"], f"{where}.kind"),
            "extractor": _pattern_string(
                capture["extractor"],
                _STABLE_ID,
                f"{where}.extractor",
                max_length=256,
            ),
            "endpoint_sha256": _sha256(
                capture["endpoint_sha256"], f"{where}.endpoint_sha256"
            ),
            "facts": _canonical_value(facts),
        }

    _exact_fields(
        capture,
        {"state", "kind", "extractor", "error"},
        {"blocked_by"},
        where,
    )
    result = {
        "state": state,
        "kind": _pipeline_kind(capture["kind"], f"{where}.kind"),
        "extractor": _pattern_string(
            capture["extractor"],
            _STABLE_ID,
            f"{where}.extractor",
            max_length=256,
        ),
        "error": _nonempty_string(
            capture["error"], f"{where}.error", max_length=8192
        ),
    }
    if "blocked_by" in capture:
        result["blocked_by"] = _string_list(
            capture["blocked_by"],
            f"{where}.blocked_by",
            nonempty=True,
            item_max_length=1024,
        )
    return result


def _counterexample(value: Any, where: str) -> dict[str, Any]:
    counterexample = _mapping(value, where)
    _exact_fields(
        counterexample,
        {
            "tag",
            "cause",
            "first_difference",
            "pair_sha256",
            "replay_sha256",
            "validator",
        },
        set(),
        where,
    )
    if counterexample["tag"] != "Validated":
        raise TraceError(f"{where}.tag: expected 'Validated'")
    validator = _mapping(counterexample["validator"], f"{where}.validator")
    _exact_fields(validator, {"id", "build_sha256"}, set(), f"{where}.validator")
    return {
        "tag": "Validated",
        "cause": _pattern_string(
            counterexample["cause"],
            _STABLE_ID,
            f"{where}.cause",
            max_length=256,
        ),
        "first_difference": _event(
            counterexample["first_difference"], f"{where}.first_difference"
        ),
        "pair_sha256": _sha256(
            counterexample["pair_sha256"], f"{where}.pair_sha256"
        ),
        "replay_sha256": _sha256(
            counterexample["replay_sha256"], f"{where}.replay_sha256"
        ),
        "validator": {
            "id": _pattern_string(
                validator["id"],
                _STABLE_ID,
                f"{where}.validator.id",
                max_length=256,
            ),
            "build_sha256": _sha256(
                validator["build_sha256"], f"{where}.validator.build_sha256"
            ),
        },
    }


def _blocker(value: Any, where: str) -> dict[str, Any]:
    blocker = _mapping(value, where)
    _exact_fields(
        blocker, {"scope", "reason", "source"}, {"detail_sha256"}, where
    )
    result = {
        "scope": _enum(blocker["scope"], BLOCKER_SCOPES, f"{where}.scope"),
        "reason": _pattern_string(
            blocker["reason"],
            _STABLE_ID,
            f"{where}.reason",
            max_length=256,
        ),
        "source": _pattern_string(
            blocker["source"], _STABLE_ID, f"{where}.source", max_length=256
        ),
    }
    if "detail_sha256" in blocker:
        result["detail_sha256"] = _sha256(
            blocker["detail_sha256"], f"{where}.detail_sha256"
        )
    return result


def _record(value: Any, where: str) -> dict[str, Any]:
    record = _mapping(value, where)
    tag = _nonempty_string(record.get("tag"), f"{where}.tag")
    if tag == "PipelineCapture":
        _exact_fields(record, {"tag", "pipeline", "capture"}, set(), where)
        return {
            "tag": tag,
            "pipeline": _pattern_string(
                record["pipeline"],
                checkpoint_model.IDENTIFIER,
                f"{where}.pipeline",
                max_length=128,
            ),
            "capture": _capture(record["capture"], f"{where}.capture"),
        }
    if tag == "RequiredChecks":
        _exact_fields(
            record,
            {"tag", "event_coverage", "all_required_gates_closed"},
            set(),
            where,
        )
        return {
            "tag": tag,
            "event_coverage": _event_list(
                record["event_coverage"], f"{where}.event_coverage"
            ),
            "all_required_gates_closed": _boolean(
                record["all_required_gates_closed"],
                f"{where}.all_required_gates_closed",
            ),
        }
    if tag == "ValidatedCounterexample":
        _exact_fields(record, {"tag", "counterexample"}, set(), where)
        return {
            "tag": tag,
            "counterexample": _counterexample(
                record["counterexample"], f"{where}.counterexample"
            ),
        }
    if tag == "Blocker":
        _exact_fields(record, {"tag", "blocker"}, set(), where)
        return {
            "tag": tag,
            "blocker": _blocker(record["blocker"], f"{where}.blocker"),
        }
    if tag == "FinalAxes":
        _exact_fields(record, {"tag", "deployment", "policy"}, set(), where)
        deployment = _nonempty_string(record["deployment"], f"{where}.deployment")
        if deployment != "Open":
            raise TraceError(f"{where}.deployment: expected 'Open'")
        return {
            "tag": tag,
            "deployment": deployment,
            "policy": _enum(record["policy"], POLICY_STATES, f"{where}.policy"),
        }
    raise TraceError(f"{where}.tag: unknown trace record tag {tag!r}")


def validate_fragment(value: Any, *, source: str = "fragment") -> dict[str, Any]:
    """Validate and normalize one already-decoded trace fragment."""

    fragment = _mapping(value, source)
    _require_strict_value(fragment, source)
    _reject_expectation_fields(fragment, source)
    _exact_fields(fragment, {"format", "session", "case", "entry", "record"}, set(), source)
    if fragment["format"] != FRAGMENT_FORMAT:
        raise TraceError(
            f"{source}.format: expected {FRAGMENT_FORMAT!r}, got {fragment['format']!r}"
        )
    return {
        "format": FRAGMENT_FORMAT,
        "session": _pattern_string(
            fragment["session"], _SESSION_ID, f"{source}.session", max_length=256
        ),
        "case": _pattern_string(
            fragment["case"], _CASE_ID, f"{source}.case", max_length=512
        ),
        "entry": _pattern_string(
            fragment["entry"],
            checkpoint_model.MLIR_SYMBOL,
            f"{source}.entry",
            max_length=256,
        ),
        "record": _record(fragment["record"], f"{source}.record"),
    }


def parse_fragment(raw: bytes, *, source: str = "fragment") -> dict[str, Any]:
    """Parse one strict-YAML fragment from bytes."""

    if len(raw) > _MAX_FRAGMENT_BYTES:
        raise TraceError(
            f"{source}: fragment is larger than {_MAX_FRAGMENT_BYTES} bytes"
        )
    value = _strict_yaml_load(raw, source=source)
    return validate_fragment(value, source=source)


def load_fragment(path: Path) -> dict[str, Any]:
    """Load a fragment file; Snapshot files fail the closed fragment schema."""

    try:
        with path.open("rb") as stream:
            raw = stream.read(_MAX_FRAGMENT_BYTES + 1)
    except OSError as error:
        raise TraceError(f"{path}: cannot read trace fragment: {error}") from error
    if len(raw) > _MAX_FRAGMENT_BYTES:
        raise TraceError(
            f"{path}: fragment is larger than {_MAX_FRAGMENT_BYTES} bytes"
        )
    return parse_fragment(raw, source=str(path))


def assemble_fragments(
    fragments: Iterable[Mapping[str, Any]],
    *,
    sensitivity: str = "Restricted",
) -> dict[str, Any]:
    """Aggregate typed fragments into one deterministic verification trace."""

    if sensitivity not in SENSITIVITIES:
        raise TraceError(
            f"sensitivity: expected one of {sorted(SENSITIVITIES)}, got {sensitivity!r}"
        )

    normalized: list[dict[str, Any]] = []
    aggregate_nodes = 0
    aggregate_text_bytes = 0
    for index, fragment in enumerate(fragments):
        if index >= _MAX_FRAGMENTS:
            raise TraceError(f"more than {_MAX_FRAGMENTS} fragments are forbidden")
        candidate = validate_fragment(fragment, source=f"fragments[{index}]")
        nodes, text_bytes = _require_strict_value(
            candidate, f"fragments[{index}]"
        )
        aggregate_nodes += nodes
        aggregate_text_bytes += text_bytes
        if aggregate_nodes > _MAX_YAML_NODES:
            raise TraceError("aggregate fragment YAML node limit exceeded")
        if aggregate_text_bytes > _MAX_FRAGMENT_BYTES:
            raise TraceError("aggregate fragment input exceeds 4 MiB limit")
        normalized.append(candidate)
    if not normalized:
        raise TraceError("at least one trace fragment is required")

    identity = (
        normalized[0]["session"],
        normalized[0]["case"],
        normalized[0]["entry"],
    )
    captures: dict[str, dict[str, Any]] = {}
    required_checks: dict[str, Any] | None = None
    counterexample: dict[str, Any] | None = None
    blockers: list[dict[str, Any]] = []
    final_axes: dict[str, Any] | None = None

    for index, fragment in enumerate(normalized):
        candidate_identity = (
            fragment["session"],
            fragment["case"],
            fragment["entry"],
        )
        if candidate_identity != identity:
            raise TraceError(
                f"fragments[{index}]: session/case/entry does not match the first fragment"
            )
        record = fragment["record"]
        tag = record["tag"]
        if tag == "PipelineCapture":
            pipeline = record["pipeline"]
            if pipeline in captures:
                raise TraceError(f"duplicate PipelineCapture for {pipeline!r}")
            captures[pipeline] = record["capture"]
        elif tag == "RequiredChecks":
            if required_checks is not None:
                raise TraceError("duplicate RequiredChecks record")
            required_checks = record
        elif tag == "ValidatedCounterexample":
            if counterexample is not None:
                raise TraceError("duplicate ValidatedCounterexample record")
            counterexample = record["counterexample"]
        elif tag == "Blocker":
            blockers.append(record["blocker"])
        elif tag == "FinalAxes":
            if final_axes is not None:
                raise TraceError("duplicate FinalAxes record")
            final_axes = record
        else:  # validate_fragment makes this unreachable.
            raise AssertionError(f"unhandled trace record {tag!r}")

    if not captures:
        raise TraceError("at least one PipelineCapture record is required")
    if required_checks is None:
        raise TraceError("exactly one RequiredChecks record is required")
    if final_axes is None:
        raise TraceError("exactly one FinalAxes record is required")

    blocker_keys = [checkpoint_model.canonical_bytes(item) for item in blockers]
    if len(blocker_keys) != len(set(blocker_keys)):
        raise TraceError("duplicate Blocker records are forbidden")
    blockers.sort(key=checkpoint_model.canonical_bytes)

    trace = {
        "format": TRACE_FORMAT,
        "case": identity[1],
        "entry": identity[2],
        "authority": TRACE_AUTHORITY,
        "sensitivity": sensitivity,
        "captures": {key: captures[key] for key in sorted(captures)},
        "decision": {
            "event_coverage": required_checks["event_coverage"],
            "counterexample": counterexample or {"tag": "None"},
            "blockers": blockers,
            "all_required_gates_closed": required_checks[
                "all_required_gates_closed"
            ],
            "deployment": final_axes["deployment"],
            "policy": final_axes["policy"],
        },
    }
    _reject_expectation_fields(trace, "trace")
    # The reusable API returns only traces that are themselves admissible to
    # the bounded C wire, not merely aggregates of individually valid parts.
    render_trace(trace)
    return trace


def assemble_fragment_files(
    paths: Sequence[Path], *, sensitivity: str = "Restricted"
) -> dict[str, Any]:
    """Load and assemble fragment files without reading any snapshot."""

    def bounded_fragments() -> Iterable[dict[str, Any]]:
        aggregate_bytes = 0
        for path in paths:
            remaining = _MAX_FRAGMENT_BYTES - aggregate_bytes
            try:
                with path.open("rb") as stream:
                    raw = stream.read(remaining + 1)
            except OSError as error:
                raise TraceError(
                    f"{path}: cannot read trace fragment: {error}"
                ) from error
            if len(raw) > remaining:
                raise TraceError("aggregate fragment input exceeds 4 MiB limit")
            aggregate_bytes += len(raw)
            yield parse_fragment(raw, source=str(path))

    return assemble_fragments(
        bounded_fragments(), sensitivity=sensitivity
    )


def render_trace(trace: Mapping[str, Any]) -> bytes:
    """Render deterministic, strict YAML suitable for the C verifier."""

    _require_strict_value(trace, "trace")
    _reject_expectation_fields(trace, "trace")
    rendered = yaml.dump(
        dict(trace),
        Dumper=_NoAliasDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=1000,
    ).encode("utf-8")
    _strict_yaml_load(rendered, source="assembled trace")
    return rendered


def _atomic_write(path: Path, raw: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
    except OSError as error:
        raise TraceError(f"{path}: cannot write assembled trace: {error}") from error


def _exclusive_private_write(path: Path, raw: bytes) -> None:
    """Create one Restricted trace without following or replacing its target."""

    descriptor = -1
    created = False
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, flags, 0o600)
        created = True
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        if descriptor >= 0:
            os.close(descriptor)
        if created:
            try:
                path.unlink()
            except OSError:
                pass
        if isinstance(error, FileExistsError):
            raise TraceError(
                f"{path}: refusing to overwrite an existing Restricted trace"
            ) from error
        raise TraceError(
            f"{path}: cannot create Restricted trace securely: {error}"
        ) from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fixture-trace",
        description="Assemble expectation-blind SPS harness trace fragments.",
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    assemble = subparsers.add_parser("assemble", allow_abbrev=False)
    assemble.add_argument(
        "--sensitivity",
        choices=sorted(SENSITIVITIES),
        default="Restricted",
    )
    assemble.add_argument("-o", "--output", default="-")
    assemble.add_argument("fragments", nargs="+", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command != "assemble":
            parser.error(f"unknown command {args.command!r}")
        trace = assemble_fragment_files(
            args.fragments, sensitivity=args.sensitivity
        )
        raw = render_trace(trace)
        if args.sensitivity == "Restricted" and args.output == "-":
            raise TraceError(
                "Restricted traces require an explicit output file; stdout is forbidden"
            )
        if args.output == "-":
            sys.stdout.buffer.write(raw)
        elif args.sensitivity == "Restricted":
            _exclusive_private_write(Path(args.output), raw)
        else:
            _atomic_write(Path(args.output), raw)
    except TraceError as error:
        print(f"fixture-trace: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
