#!/usr/bin/env python3
"""Minimal Snapshot V3 expectations and static checkpoint inventory.

Snapshots describe expected security behavior and sparse endpoint properties.
Lit owns execution: commands, capabilities, inputs, artifact paths, and test
ownership are deliberately absent from the YAML contract and are discovered by
the inventory scanner.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import yaml
from yaml.tokens import AliasToken, AnchorToken, TagToken


FORMAT_ID = "SPS-Harness-Fixture-Snapshot-v3"
OBSERVATION_FORMAT_ID = "SPS-Harness-Pipeline-Endpoint-Observation-v1"
IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
STABLE_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]*\Z")
MLIR_SYMBOL = re.compile(r"[A-Za-z_.$][A-Za-z0-9_.$-]*\Z")
ROOT_TYPE = re.compile(r"[A-Za-z][A-Za-z0-9]*V[0-9]+\Z")
FIELD_PATH = re.compile(r"[A-Za-z0-9_.-]+\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")

PIPELINE_KINDS = frozenset(
    {
        "mlir",
        "llvm-ir",
        "mir",
        "assembly",
        "object",
        "bytes",
        "diagnostic",
        "json",
        "relation-reference",
    }
)
STRUCTURAL_KINDS = frozenset({"mlir", "llvm-ir", "mir", "assembly", "object"})
COMPACT_MATCHER_OPERATORS = frozenset(
    {"equals", "contains", "excludes", "count", "ordered"}
)
NORMALIZED_MATCHER_OPERATORS = frozenset(
    {"equals", "contains_all", "not_contains_any", "count", "ordered_subsequence"}
)
STRUCTURAL_EXTRACTORS = {
    "mlir": ("mlir", "mlir-structure-v1"),
    "llvm-ir": ("llvm-ir", "llvm-ir-structure-v1"),
    "mir": ("mir", "mir-structure-v1"),
    "assembly": ("assembly", "assembly-structure-v1"),
    "object": ("object-inventory", "object-inventory-v1"),
}
RELATION_REFERENCE_PROFILE = "SPS-Reference-Relation-v1"
RELATION_REFERENCE_FACTS = frozenset(
    {
        "query.admission-nonempty",
        "query.high-variation",
        "query.terminal-output-surface",
        "query.audit-all",
        "query.audit-all-first-difference",
        "backend.agreement",
    }
)
REQUIRED_RELATION_REFERENCE_FACTS = RELATION_REFERENCE_FACTS - {
    "query.audit-all-first-difference"
}

# These are exactly the fields in the fixed Theta_ct event constructors in SPS
# section 7.  Site/occurrence coordinates are intentionally not selectors:
# snapshots name semantic fields, not raw trace locations.
EVENT_FIELDS = {
    "BranchSuccessor": frozenset({"successor"}),
    "SwitchSuccessor": frozenset({"successor"}),
    "CalleeChoice": frozenset({"callee"}),
    "LoopContinuation": frozenset({"continueOrExit"}),
    "Failure": frozenset({"class"}),
    "Termination": frozenset({"returnClass"}),
    "BoundExhausted": frozenset({"boundId"}),
    "UBRisk": frozenset({"reasonClass"}),
    "Memory": frozenset(
        {"allocationClass", "offsetClass", "width", "addressSpace", "readOrWrite"}
    ),
    "Transfer": frozenset(
        {"source", "destinations", "width", "representation", "valueBytes", "metadata"}
    ),
    "Output": frozenset({"outputId", "footprint", "valueBytes"}),
    "Release": frozenset({"releaseId", "releaseOrdinal", "valueBytes", "footprint"}),
    "Error": frozenset({"errorFieldId", "class", "payload"}),
    "Latency": frozenset({"configuredClass"}),
    "ContractMeta": frozenset({"contractId", "metadataFieldId", "typedValue"}),
}
EVENT_ID_KINDS = frozenset({"Output", "Error", "Release", "BoundExhausted"})


class CheckpointError(ValueError):
    """A Snapshot V3, inventory, digest, or observation contract is invalid."""


@lru_cache(maxsize=1)
def _model_statuses() -> frozenset[str]:
    """Read the closed ModelStatus union from the pinned SPS registry."""

    try:
        import sps_interfaces

        registry = sps_interfaces.load_default_registry()
        return frozenset(registry.union_variants("ModelStatusV2"))
    except (ImportError, OSError, ValueError) as error:
        raise CheckpointError(
            f"pinned SPS ModelStatusV2 registry is unavailable: {error}"
        ) from error


class _StrictLoader(yaml.SafeLoader):
    """Safe YAML loader that also rejects duplicate keys and merge semantics."""


def _construct_mapping(
    loader: _StrictLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge" or key_node.value == "<<":
            raise yaml.constructor.ConstructorError(
                None, None, "merge keys are not allowed", key_node.start_mark
            )
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise yaml.constructor.ConstructorError(
                None, None, "mapping keys must be strings", key_node.start_mark
            )
        if key in result:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _require_yaml_value(value: Any, where: str = "$") -> None:
    """Reject YAML-only scalar types and values outside the JSON data model."""

    if value is None or isinstance(value, float):
        raise CheckpointError(f"{where}: null and floating-point scalars are forbidden")
    if isinstance(value, (str, bool)) or (
        isinstance(value, int) and not isinstance(value, bool)
    ):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_yaml_value(item, f"{where}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CheckpointError(f"{where}: mapping keys must be strings")
            _require_yaml_value(item, f"{where}.{key}")
        return
    raise CheckpointError(
        f"{where}: YAML scalar type {type(value).__name__} is forbidden"
    )


def strict_yaml_load(raw: bytes, *, source: str = "snapshot") -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise CheckpointError(f"{source}: UTF-8 BOM is forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CheckpointError(f"{source}: invalid UTF-8") from error
    try:
        for token in yaml.scan(text):
            if isinstance(token, (AliasToken, AnchorToken, TagToken)):
                raise CheckpointError(
                    f"{source}: aliases, anchors, and explicit tags are forbidden"
                )
        value = yaml.load(text, Loader=_StrictLoader)
    except CheckpointError:
        raise
    except yaml.YAMLError as error:
        raise CheckpointError(f"{source}: invalid strict YAML: {error}") from error
    _require_yaml_value(value)
    if not isinstance(value, dict):
        raise CheckpointError(f"{source}: top-level value must be a mapping")
    return value


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise CheckpointError(f"value is not canonical-JSON encodable: {error}") from error


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def byte_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _exact_fields(
    value: Mapping[str, Any], required: set[str], optional: set[str], where: str
) -> None:
    actual = set(value)
    allowed = required | optional
    if not required <= actual or not actual <= allowed:
        raise CheckpointError(
            f"{where}: wrong fields; missing={sorted(required - actual)}, "
            f"extra={sorted(actual - allowed)}"
        )


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CheckpointError(f"{where}: expected mapping")
    return value


def _nonempty_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CheckpointError(f"{where}: expected nonempty string")
    return value


def _string_list(
    value: Any, where: str, *, nonempty: bool = True, canonical: bool = False
) -> tuple[str, ...]:
    if not isinstance(value, list) or (nonempty and not value):
        raise CheckpointError(f"{where}: expected {'nonempty ' if nonempty else ''}list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise CheckpointError(f"{where}: every item must be a nonempty string")
    if canonical and value != sorted(set(value)):
        raise CheckpointError(f"{where}: must be sorted and duplicate-free")
    return tuple(value)


def resolve_root_path(
    root: Path,
    value: Any,
    where: str,
    *,
    must_exist: bool = True,
    allow_directory: bool = False,
) -> Path:
    text = _nonempty_string(value, where)
    if "\\" in text:
        raise CheckpointError(f"{where}: paths must use POSIX separators")
    pure = PurePosixPath(text)
    if (
        pure.is_absolute()
        or not pure.parts
        or pure.as_posix() != text
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise CheckpointError(f"{where}: path must be normalized and harness-root-relative")
    root = root.resolve()
    resolved = (root / Path(*pure.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise CheckpointError(f"{where}: path escapes the harness root") from error
    if must_exist and not resolved.exists():
        raise CheckpointError(f"{where}: path does not exist: {text}")
    if must_exist and not allow_directory and not resolved.is_file():
        raise CheckpointError(f"{where}: path must name a file: {text}")
    return resolved


@dataclass(frozen=True)
class DigestBinding:
    manifest: str
    field: str


@dataclass(frozen=True)
class EventExpectation:
    kind: str
    field: str
    id: str | None = None
    first_bad: bool = False


@dataclass(frozen=True)
class FinalExpectation:
    status: str
    deployment: str
    policy: str
    because: str
    bad_state: str | None = None
    reason: str | None = None
    events: tuple[EventExpectation, ...] = ()
    reference: str | None = None

    @property
    def model(self) -> Mapping[str, Any]:
        result: dict[str, Any] = {"status": self.status}
        if self.bad_state is not None:
            result["bad_state"] = self.bad_state
        if self.reason is not None:
            result["reason"] = self.reason
        return result


@dataclass(frozen=True)
class PipelineV3:
    id: str
    kind: str
    properties: Mapping[str, Any] | None = None
    function: str | None = None
    digest: DigestBinding | None = None
    root_type: str | None = None
    stage_id: str | None = None
    profile: str | None = None
    # These fields are derived from lit by build_inventory; they are never
    # accepted in snapshot YAML.
    test: str | None = None
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class SnapshotV3:
    path: Path
    root: Path
    case: str
    entry: str
    c_evidence: tuple[str, ...]
    secret: tuple[Mapping[str, Any], ...]
    public: tuple[Mapping[str, Any], ...]
    allowed: tuple[str, ...]
    final: FinalExpectation
    pipelines: Mapping[str, PipelineV3]
    raw: Mapping[str, Any]

    @property
    def expected_model_status(self) -> Mapping[str, Any]:
        return self.final.model

    @property
    def expected_deployment(self) -> str:
        return self.final.deployment

    @property
    def expected_policy(self) -> str:
        return self.final.policy

    @property
    def events(self) -> tuple[EventExpectation, ...]:
        return self.final.events

    @property
    def reference(self) -> str | None:
        return self.final.reference


@dataclass(frozen=True)
class RunBinding:
    test: str
    mode: str
    snapshot: str
    pipeline: str
    input_paths: tuple[tuple[str, str], ...]
    producer_arguments: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class FinalizerBinding:
    test: str
    declared_test: str
    line: int


@dataclass(frozen=True)
class DispatchBinding:
    test: str
    pipeline: str
    producer_arguments: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class Inventory:
    snapshots: tuple[SnapshotV3, ...]
    run_bindings: tuple[RunBinding, ...]
    finalizers: tuple[FinalizerBinding, ...]


def _parse_digest_binding(
    value: Any, root: Path, where: str
) -> DigestBinding:
    mapping = _mapping(value, where)
    _exact_fields(mapping, {"manifest", "field"}, set(), where)
    manifest = _nonempty_string(mapping["manifest"], f"{where}.manifest")
    resolve_root_path(root, manifest, f"{where}.manifest")
    field = _nonempty_string(mapping["field"], f"{where}.field")
    if not FIELD_PATH.fullmatch(field):
        raise CheckpointError(f"{where}.field: malformed manifest field path")
    return DigestBinding(manifest=manifest, field=field)


def parse_digest_binding(value: Any, root: Path, where: str = "digest_from") -> DigestBinding:
    """Public runner adapter for a harness-root-relative digest binding."""

    return _parse_digest_binding(value, Path(root).resolve(), where)


def _validate_count(value: Any, where: str) -> Mapping[str, int]:
    count = _mapping(value, where)
    if not count or not set(count) <= {"eq", "min", "max"}:
        raise CheckpointError(f"{where}: expected a nonempty subset of eq/min/max")
    for key, item in count.items():
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise CheckpointError(f"{where}.{key}: expected natural number")
    if "eq" in count and (
        ("min" in count and count["eq"] < count["min"])
        or ("max" in count and count["eq"] > count["max"])
    ):
        raise CheckpointError(f"{where}: inconsistent exact bound")
    if "min" in count and "max" in count and count["min"] > count["max"]:
        raise CheckpointError(f"{where}: minimum exceeds maximum")
    return dict(count)


def _validate_normalized_matcher(value: Any, where: str) -> Mapping[str, Any]:
    matcher = _mapping(value, where)
    if not matcher or not set(matcher) <= NORMALIZED_MATCHER_OPERATORS:
        raise CheckpointError(
            f"{where}: matcher must use only {sorted(NORMALIZED_MATCHER_OPERATORS)}"
        )
    for operator in {"contains_all", "not_contains_any", "ordered_subsequence"}:
        if operator in matcher and not isinstance(matcher[operator], list):
            raise CheckpointError(f"{where}.{operator}: expected list")
    if "count" in matcher:
        _validate_count(matcher["count"], f"{where}.count")
    return dict(matcher)


def validate_matchers(properties: Any, where: str) -> Mapping[str, Any]:
    """Validate the normalized matcher form consumed by extractors."""

    mapping = _mapping(properties, where)
    if not mapping:
        raise CheckpointError(f"{where}: properties must be nonempty")
    result: dict[str, Any] = {}
    for fact, matcher in mapping.items():
        if not isinstance(fact, str) or not fact:
            raise CheckpointError(f"{where}: fact names must be nonempty strings")
        result[fact] = _validate_normalized_matcher(matcher, f"{where}.{fact}")
    return result


def _normalize_properties(properties: Any, where: str) -> Mapping[str, Any]:
    """Translate compact snapshot operators into extractor matcher operators."""

    mapping = _mapping(properties, where)
    if not mapping:
        raise CheckpointError(f"{where}: properties must be nonempty")
    operator_names = {
        "contains": "contains_all",
        "excludes": "not_contains_any",
        "ordered": "ordered_subsequence",
        "equals": "equals",
        "count": "count",
    }
    normalized: dict[str, Any] = {}
    for fact, raw_matcher in mapping.items():
        if not isinstance(fact, str) or not fact:
            raise CheckpointError(f"{where}: fact names must be nonempty strings")
        matcher = _mapping(raw_matcher, f"{where}.{fact}")
        if not matcher or not set(matcher) <= COMPACT_MATCHER_OPERATORS:
            raise CheckpointError(
                f"{where}.{fact}: matcher must use only "
                f"{sorted(COMPACT_MATCHER_OPERATORS)}"
            )
        row: dict[str, Any] = {}
        for compact, value in matcher.items():
            normalized_name = operator_names[compact]
            if compact in {"contains", "excludes", "ordered"}:
                if not isinstance(value, list):
                    raise CheckpointError(f"{where}.{fact}.{compact}: expected list")
                row[normalized_name] = list(value)
            elif compact == "count":
                row[normalized_name] = _validate_count(
                    value, f"{where}.{fact}.count"
                )
            else:
                row[normalized_name] = value
        normalized[fact] = row
    return validate_matchers(normalized, where)


def _validate_sps_root(value: Any, root_type: str, where: str) -> None:
    try:
        import sps_interfaces

        registry = sps_interfaces.load_default_registry()
        registry.validate_root(value, root_type)
        failures = registry.semantic_failures(value, root_type)
    except ImportError as error:
        raise CheckpointError(
            f"{where}: vendored SPS registry validator is unavailable"
        ) from error
    except ValueError as error:
        raise CheckpointError(f"{where}: invalid {root_type}: {error}") from error
    if failures:
        raise CheckpointError(
            f"{where}: {root_type} semantic validation failed: "
            + ", ".join(failures)
        )


def _snapshot_relative_path(
    snapshot_path: Path, root: Path, value: Any, where: str
) -> tuple[str, Path]:
    text = _nonempty_string(value, where)
    if "\\" in text:
        raise CheckpointError(f"{where}: paths must use POSIX separators")
    pure = PurePosixPath(text)
    if (
        pure.is_absolute()
        or not pure.parts
        or pure.as_posix() != text
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise CheckpointError(f"{where}: path must be normalized and snapshot-relative")
    root = root.resolve()
    resolved = (snapshot_path.parent / Path(*pure.parts)).resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as error:
        raise CheckpointError(f"{where}: path escapes the harness root") from error
    if not resolved.is_file():
        raise CheckpointError(f"{where}: path does not exist: {text}")
    return relative, resolved


def _parse_snapshot_digest_binding(
    value: Any, snapshot_path: Path, root: Path, where: str
) -> DigestBinding:
    mapping = _mapping(value, where)
    _exact_fields(mapping, {"manifest", "field"}, set(), where)
    manifest, _ = _snapshot_relative_path(
        snapshot_path, root, mapping["manifest"], f"{where}.manifest"
    )
    field = _nonempty_string(mapping["field"], f"{where}.field")
    if not FIELD_PATH.fullmatch(field):
        raise CheckpointError(f"{where}.field: malformed manifest field path")
    return DigestBinding(manifest=manifest, field=field)


def _parse_event(value: Any, where: str) -> EventExpectation:
    mapping = _mapping(value, where)
    _exact_fields(mapping, {"kind", "field"}, {"id", "first_bad"}, where)
    kind = _nonempty_string(mapping["kind"], f"{where}.kind")
    if kind not in EVENT_FIELDS:
        raise CheckpointError(f"{where}.kind: unknown Theta_ct event kind {kind!r}")
    field = _nonempty_string(mapping["field"], f"{where}.field")
    if field not in EVENT_FIELDS[kind]:
        raise CheckpointError(
            f"{where}.field: {field!r} is not a field of {kind}; "
            f"expected one of {sorted(EVENT_FIELDS[kind])}"
        )
    logical_id: str | None = None
    if "id" in mapping:
        if kind not in EVENT_ID_KINDS:
            raise CheckpointError(
                f"{where}.id: logical IDs apply only to outputs, errors, releases, or bounds"
            )
        logical_id = _nonempty_string(mapping["id"], f"{where}.id")
        if not STABLE_ID.fullmatch(logical_id):
            raise CheckpointError(f"{where}.id: malformed stable identifier")
    first_bad = False
    if "first_bad" in mapping:
        if mapping["first_bad"] is not True:
            raise CheckpointError(f"{where}.first_bad: when present, must be true")
        first_bad = True
    return EventExpectation(kind, field, logical_id, first_bad)


def _parse_final(value: Any, where: str) -> FinalExpectation:
    final = _mapping(value, where)
    _exact_fields(
        final,
        {"model", "deployment", "policy", "because"},
        {"events", "reference"},
        where,
    )
    model_where = f"{where}.model"
    model = _mapping(final["model"], model_where)
    status = model.get("status")
    model_statuses = _model_statuses()
    if status not in model_statuses:
        raise CheckpointError(
            f"{model_where}.status: expected one of {sorted(model_statuses)}"
        )
    if status == "Proved":
        _exact_fields(model, {"status"}, set(), model_where)
        bad_state = reason = None
    elif status == "Counterexample":
        _exact_fields(model, {"status", "bad_state"}, set(), model_where)
        bad_state = _nonempty_string(model["bad_state"], f"{model_where}.bad_state")
        if not STABLE_ID.fullmatch(bad_state):
            raise CheckpointError(f"{model_where}.bad_state: malformed stable identifier")
        reason = None
    else:
        _exact_fields(model, {"status", "reason"}, set(), model_where)
        reason = _nonempty_string(model["reason"], f"{model_where}.reason")
        _validate_sps_root(
            {"reasonClassId": reason},
            "PublicDispositionReasonV2",
            f"{model_where}.reason",
        )
        bad_state = None

    if final["deployment"] != "Open":
        raise CheckpointError(f"{where}.deployment: Snapshot V3 requires Open")
    if final["policy"] != "Complete":
        raise CheckpointError(f"{where}.policy: Snapshot V3 requires Complete")
    because = _nonempty_string(final["because"], f"{where}.because")
    raw_events = final.get("events", [])
    if not isinstance(raw_events, list):
        raise CheckpointError(f"{where}.events: expected list")
    events = tuple(
        _parse_event(item, f"{where}.events[{index}]")
        for index, item in enumerate(raw_events)
    )
    if status in {"Proved", "Counterexample"} and not events:
        raise CheckpointError(f"{where}.events: {status} requires event coverage")
    first_bad_count = sum(event.first_bad for event in events)
    if status == "Counterexample" and first_bad_count != 1:
        raise CheckpointError(
            f"{where}.events: Counterexample requires exactly one first_bad event"
        )
    if first_bad_count and status != "Counterexample":
        raise CheckpointError(f"{where}.events: first_bad is legal only for Counterexample")
    if status == "Counterexample":
        first_bad_event = next(event for event in events if event.first_bad)
        if first_bad_event.kind in EVENT_ID_KINDS and first_bad_event.id is None:
            raise CheckpointError(
                f"{where}.events: first_bad {first_bad_event.kind} event "
                "requires a logical ID"
            )

    reference = None
    if "reference" in final:
        reference = _nonempty_string(final["reference"], f"{where}.reference")
        if reference != "candidate/expected-report.json":
            raise CheckpointError(
                f"{where}.reference: candidate reference must be "
                "'candidate/expected-report.json'"
            )
    return FinalExpectation(
        status=status,
        deployment="Open",
        policy="Complete",
        because=because,
        bad_state=bad_state,
        reason=reason,
        events=events,
        reference=reference,
    )


def _parse_pipeline(
    identifier: str,
    value: Any,
    snapshot_path: Path,
    root: Path,
    entry: str,
    where: str,
) -> PipelineV3:
    if not IDENTIFIER.fullmatch(identifier):
        raise CheckpointError(f"{where}: pipeline id must be lower-kebab")
    mapping = _mapping(value, where)
    kind = mapping.get("kind")
    if kind not in PIPELINE_KINDS:
        raise CheckpointError(f"{where}.kind: expected one of {sorted(PIPELINE_KINDS)}")

    if kind in STRUCTURAL_KINDS:
        optional = {"function"} if kind != "object" else set()
        _exact_fields(mapping, {"kind", "properties"}, optional, where)
        function = None
        if kind != "object":
            function = _nonempty_string(mapping.get("function", entry), f"{where}.function")
            if not MLIR_SYMBOL.fullmatch(function):
                raise CheckpointError(f"{where}.function: malformed symbol")
        properties = _normalize_properties(mapping["properties"], f"{where}.properties")
        representation, extractor = STRUCTURAL_EXTRACTORS[str(kind)]
        try:
            from checkpoint_extractors import validate_properties

            validate_properties(representation, extractor, properties)
        except ImportError as error:
            raise CheckpointError(f"{where}: structural extractor registry is unavailable") from error
        except ValueError as error:
            raise CheckpointError(f"{where}: {error}") from error
        return PipelineV3(identifier, str(kind), properties=properties, function=function)

    if kind == "bytes":
        _exact_fields(mapping, {"kind", "digest"}, set(), where)
        digest = _parse_snapshot_digest_binding(
            mapping["digest"], snapshot_path, root, f"{where}.digest"
        )
        return PipelineV3(identifier, "bytes", digest=digest)

    if kind == "diagnostic":
        _exact_fields(mapping, {"kind", "properties"}, {"stage_id"}, where)
        default_stage_id = {
            "source-boundary": "SourceBoundaryValidation",
        }.get(identifier, identifier)
        stage_id = _nonempty_string(
            mapping.get("stage_id", default_stage_id), f"{where}.stage_id"
        )
        if not STABLE_ID.fullmatch(stage_id):
            raise CheckpointError(f"{where}.stage_id: malformed identifier")
        properties = _normalize_properties(mapping["properties"], f"{where}.properties")
        unknown = set(properties) - {"completedChecks", "findings", "blockers"}
        if unknown:
            raise CheckpointError(f"{where}.properties: unknown diagnostic facts {sorted(unknown)}")
        return PipelineV3(
            identifier, "diagnostic", properties=properties, stage_id=stage_id
        )

    if kind == "relation-reference":
        _exact_fields(mapping, {"kind", "profile", "properties"}, set(), where)
        profile = _nonempty_string(mapping["profile"], f"{where}.profile")
        if profile != RELATION_REFERENCE_PROFILE:
            raise CheckpointError(
                f"{where}.profile: unknown relation-reference profile {profile!r}"
            )
        properties = _normalize_properties(mapping["properties"], f"{where}.properties")
        unknown = set(properties) - RELATION_REFERENCE_FACTS
        if unknown:
            raise CheckpointError(
                f"{where}.properties: unknown relation-reference facts {sorted(unknown)}"
            )
        missing = REQUIRED_RELATION_REFERENCE_FACTS - set(properties)
        if missing:
            raise CheckpointError(
                f"{where}.properties: missing relation-reference facts {sorted(missing)}"
            )
        return PipelineV3(
            identifier,
            "relation-reference",
            properties=properties,
            profile=profile,
        )

    _exact_fields(mapping, {"kind", "root_type"}, set(), where)
    root_type = _nonempty_string(mapping["root_type"], f"{where}.root_type")
    if not ROOT_TYPE.fullmatch(root_type):
        raise CheckpointError(f"{where}.root_type: malformed SPS root type")
    return PipelineV3(identifier, "json", root_type=root_type)


def _snapshot_case(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to((root / "fixtures").resolve())
    except ValueError as error:
        raise CheckpointError(f"{path}: snapshot must live below fixtures/") from error
    if len(relative.parts) != 3 or relative.name != "snapshot.yaml":
        raise CheckpointError(
            f"{path}: snapshot must live at fixtures/<family>/<case>/snapshot.yaml"
        )
    return "/".join(relative.parts[:2])


def _validate_candidate_reference(
    snapshot_path: Path,
    root: Path,
    entry: str,
    final: FinalExpectation,
    where: str,
) -> None:
    if final.reference is None:
        return
    _, expected_path = _snapshot_relative_path(
        snapshot_path, root, final.reference, f"{where}.reference"
    )
    try:
        from candidate_expected_matcher import load_candidate_expectation

        envelope = load_candidate_expectation(expected_path)
    except (ImportError, OSError, ValueError) as error:
        raise CheckpointError(f"{where}.reference: invalid candidate expectation: {error}") from error
    expected = _mapping(envelope.value["expected"], f"{where}.reference.expected")
    mismatches: list[str] = []
    if expected.get("entry") != entry:
        mismatches.append(f"entry={expected.get('entry')!r}, snapshot={entry!r}")
    model = _mapping(expected.get("expected_model_status"), f"{where}.reference.model")
    if model.get("tag") != final.status:
        mismatches.append(f"model={model.get('tag')!r}, snapshot={final.status!r}")
    if final.status == "Unknown":
        reasons = model.get("args")
        sidecar_reasons = (
            [item.get("reasonClassId") for item in reasons if isinstance(item, Mapping)]
            if isinstance(reasons, list)
            else []
        )
        if sidecar_reasons != [final.reason]:
            mismatches.append(f"reason={sidecar_reasons!r}, snapshot={[final.reason]!r}")
    if final.status == "Counterexample":
        bad_states = sorted(
            {
                replay["bad_state_class"]
                for row in expected.get("audit_all_expectations", [])
                if isinstance(row, Mapping)
                for replay in [row.get("replay_expectation")]
                if isinstance(replay, Mapping)
                and replay.get("tag") == "AcceptedBadStateRequiredV2"
                and isinstance(replay.get("bad_state_class"), str)
            }
        )
        if bad_states != [final.bad_state]:
            mismatches.append(f"bad_state={bad_states!r}, snapshot={[final.bad_state]!r}")
    deployment = expected.get("expected_deployment_status")
    deployment_tag = deployment.get("tag") if isinstance(deployment, Mapping) else None
    if deployment_tag != final.deployment:
        mismatches.append(f"deployment={deployment_tag!r}, snapshot={final.deployment!r}")
    policy = expected.get("expected_policy_review_status")
    policy_tag = policy.get("tag") if isinstance(policy, Mapping) else None
    if policy_tag != final.policy:
        mismatches.append(f"policy={policy_tag!r}, snapshot={final.policy!r}")
    if mismatches:
        raise CheckpointError(
            f"{where}.reference: candidate final projection disagrees: "
            + "; ".join(mismatches)
        )


def load_snapshot(path: Path, root: Path | None = None) -> SnapshotV3:
    path = Path(path).resolve()
    root = Path(root).resolve() if root is not None else path.parents[3]
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise CheckpointError(f"{path}: cannot read snapshot: {error}") from error
    value = strict_yaml_load(raw, source=str(path))
    _exact_fields(
        value,
        {"format_id", "entry", "c_evidence", "secret", "public", "expect"},
        {"allowed"},
        str(path),
    )
    if value["format_id"] != FORMAT_ID:
        raise CheckpointError(f"{path}: format_id must be {FORMAT_ID!r}")
    entry = _nonempty_string(value["entry"], f"{path}.entry")
    if not MLIR_SYMBOL.fullmatch(entry):
        raise CheckpointError(f"{path}.entry: malformed MLIR symbol")
    c_evidence = _string_list(value["c_evidence"], f"{path}.c_evidence")
    if not isinstance(value["secret"], list) or any(
        not isinstance(item, Mapping) for item in value["secret"]
    ):
        raise CheckpointError(f"{path}.secret: expected list of mappings")
    if not isinstance(value["public"], list) or not value["public"] or any(
        not isinstance(item, Mapping) for item in value["public"]
    ):
        raise CheckpointError(f"{path}.public: expected nonempty list of mappings")
    allowed = (
        _string_list(value["allowed"], f"{path}.allowed")
        if "allowed" in value
        else ()
    )
    expect = _mapping(value["expect"], f"{path}.expect")
    _exact_fields(expect, {"final", "pipelines"}, set(), f"{path}.expect")
    final = _parse_final(expect["final"], f"{path}.expect.final")
    _validate_candidate_reference(path, root, entry, final, f"{path}.expect.final")
    pipelines_value = _mapping(expect["pipelines"], f"{path}.expect.pipelines")
    if not pipelines_value:
        raise CheckpointError(f"{path}.expect.pipelines: must be nonempty")
    pipelines = {
        identifier: _parse_pipeline(
            identifier,
            pipeline,
            path,
            root,
            entry,
            f"{path}.expect.pipelines.{identifier}",
        )
        for identifier, pipeline in pipelines_value.items()
    }
    return SnapshotV3(
        path=path,
        root=root,
        case=_snapshot_case(path, root),
        entry=entry,
        c_evidence=c_evidence,
        secret=tuple(dict(item) for item in value["secret"]),
        public=tuple(dict(item) for item in value["public"]),
        allowed=allowed,
        final=final,
        pipelines=pipelines,
        raw=value,
    )


def load_snapshots(root: Path) -> tuple[SnapshotV3, ...]:
    root = Path(root).resolve()
    paths = sorted((root / "fixtures").rglob("snapshot.yaml"))
    if not paths:
        raise CheckpointError(f"{root}: no fixture snapshots found")
    return tuple(load_snapshot(path, root) for path in paths)


def outcome_totals(snapshots: Iterable[SnapshotV3]) -> dict[str, int]:
    totals = {status: 0 for status in sorted(_model_statuses())}
    for snapshot in snapshots:
        totals[snapshot.final.status] += 1
    return totals


_DIRECTIVE = re.compile(r"^\s*(?://|#)\s*(RUN|REQUIRES):\s*(.*?)\s*$")


def _directives(path: Path) -> tuple[list[tuple[int, str]], set[str]]:
    runs: list[tuple[int, str]] = []
    requires: set[str] = set()
    pending: str | None = None
    pending_line = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _DIRECTIVE.match(line)
        if not match:
            continue
        kind, body = match.groups()
        if kind == "REQUIRES":
            requires.update(item.strip() for item in body.split(",") if item.strip())
            continue
        if pending is not None:
            body = pending + " " + body
            line_number = pending_line
            pending = None
        if body.endswith("\\"):
            pending = body[:-1].rstrip()
            pending_line = line_number
        else:
            runs.append((line_number, body))
    if pending is not None:
        raise CheckpointError(f"{path}:{pending_line}: unterminated RUN continuation")
    return runs, requires


def _option(tokens: Sequence[str], name: str) -> str | None:
    values: list[str] = []
    for index, token in enumerate(tokens):
        if token == name and index + 1 < len(tokens):
            values.append(tokens[index + 1])
        elif token.startswith(name + "="):
            values.append(token.split("=", 1)[1])
    if not values:
        return None
    if len(values) != 1:
        raise CheckpointError(f"command repeats {name}")
    return values[0]


def _options(tokens: Sequence[str], name: str) -> tuple[str, ...]:
    values: list[str] = []
    for index, token in enumerate(tokens):
        if token == name:
            if index + 1 >= len(tokens):
                raise CheckpointError(f"command option {name} lacks a value")
            values.append(tokens[index + 1])
        elif token.startswith(name + "="):
            values.append(token.split("=", 1)[1])
    return tuple(values)


def _run_input_paths(tokens: Sequence[str]) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in _options(tokens, "--input"):
        identifier, separator, path = value.partition("=")
        if not separator or not IDENTIFIER.fullmatch(identifier) or not path:
            raise CheckpointError(
                "--input must have the form lower-kebab-id=materialized-path"
            )
        if identifier in seen:
            raise CheckpointError(f"command repeats --input mapping {identifier!r}")
        seen.add(identifier)
        result.append((identifier, path))
    return tuple(result)


def _normalize_source_path(
    value: str, *, test_relative: str, test_path: Path, root: Path
) -> str:
    if value == "%s":
        return test_relative
    if value.startswith("%S/"):
        candidate = test_path.parent / value[3:]
    elif value == "%S":
        candidate = test_path.parent
    elif value.startswith("%harness/"):
        candidate = root / value[len("%harness/") :]
    elif value.startswith("%fixtures/"):
        candidate = root / "fixtures" / value[len("%fixtures/") :]
    else:
        path = Path(value)
        candidate = path if path.is_absolute() else root / path
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise CheckpointError(f"path {value!r} escapes harness root") from error


def _is_checkpoint_command(tokens: Sequence[str]) -> int | None:
    for index, token in enumerate(tokens):
        if token == "%checkpoint-runner" or token.endswith("/checkpoint_runner.py"):
            return index
    return None


def _scan_test(
    root: Path, test_path: Path
) -> tuple[
    list[RunBinding], list[FinalizerBinding], list[DispatchBinding], set[str]
]:
    relative = test_path.resolve().relative_to(root.resolve()).as_posix()
    runs, requires = _directives(test_path)
    bindings: list[RunBinding] = []
    finalizers: list[FinalizerBinding] = []
    dispatches: list[DispatchBinding] = []
    for line, command in runs:
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError as error:
            raise CheckpointError(f"{relative}:{line}: malformed RUN command: {error}") from error
        index = _is_checkpoint_command(tokens)
        if index is None:
            command_root = _option(tokens, "--root")
            targets_root = command_root is None or command_root in {"%harness", str(root)}
            dispatched_pipeline = _option(tokens, "--checkpoint-pipeline")
        else:
            # A producer after ``--`` may have its own --root or
            # --checkpoint-pipeline arguments.  They are not runner metadata.
            boundary = tokens.index("--") if "--" in tokens else len(tokens)
            runner_tokens = tokens[:boundary]
            command_root = _option(runner_tokens, "--root")
            targets_root = command_root is None or command_root in {"%harness", str(root)}
            dispatched_pipeline = None
        if dispatched_pipeline is not None and targets_root:
            if not IDENTIFIER.fullmatch(dispatched_pipeline):
                raise CheckpointError(
                    f"{relative}:{line}: --checkpoint-pipeline must be a lower-kebab identifier"
                )
            dispatches.append(
                DispatchBinding(
                    test=relative,
                    pipeline=dispatched_pipeline,
                    producer_arguments=tuple(tokens),
                    line=line,
                )
            )
        if index is None or index + 1 >= len(tokens):
            continue
        if not targets_root:
            # Contract tests exercise checkpoint_runner against temporary roots;
            # those nested harnesses are not bindings in this inventory.
            continue
        mode = tokens[index + 1]
        tail = tokens[index + 2 :]
        if mode in {"run", "check-existing"}:
            if mode == "run" and "--" not in tail:
                raise CheckpointError(
                    f"{relative}:{line}: checkpoint run requires a literal -- producer boundary"
                )
            boundary = tail.index("--") if "--" in tail else len(tail)
            binding_options = tail[:boundary]
            producer_arguments = (
                tuple(tail[boundary + 1 :]) if boundary < len(tail) else ()
            )
            snapshot = _option(binding_options, "--snapshot")
            pipeline = _option(binding_options, "--pipeline")
            if snapshot is None or pipeline is None:
                raise CheckpointError(
                    f"{relative}:{line}: checkpoint binding requires --snapshot and --pipeline"
                )
            if not IDENTIFIER.fullmatch(pipeline):
                raise CheckpointError(
                    f"{relative}:{line}: --pipeline must be a lower-kebab identifier"
                )
            if _option(binding_options, "--endpoint") is None:
                raise CheckpointError(
                    f"{relative}:{line}: checkpoint {mode} requires --endpoint; "
                    "artifact paths are owned by lit, not snapshot YAML"
                )
            if mode == "run" and not producer_arguments:
                raise CheckpointError(
                    f"{relative}:{line}: checkpoint run requires a producer after --"
                )
            bindings.append(
                RunBinding(
                    test=relative,
                    mode=mode,
                    snapshot=_normalize_source_path(
                        snapshot, test_relative=relative, test_path=test_path, root=root
                    ),
                    pipeline=pipeline,
                    input_paths=_run_input_paths(binding_options),
                    producer_arguments=producer_arguments,
                    line=line,
                )
            )
        elif mode == "finalize":
            declared_test = _option(tail, "--test")
            records = _option(tail, "--records")
            if declared_test is None or records is None:
                raise CheckpointError(
                    f"{relative}:{line}: finalizer requires --test and --records"
                )
            finalizers.append(
                FinalizerBinding(
                    test=relative,
                    declared_test=_normalize_source_path(
                        declared_test,
                        test_relative=relative,
                        test_path=test_path,
                        root=root,
                    ),
                    line=line,
                )
            )
    return bindings, finalizers, dispatches, requires


def build_inventory(root: Path) -> Inventory:
    root = Path(root).resolve()
    loaded_snapshots = load_snapshots(root)
    declared: dict[tuple[str, str], tuple[SnapshotV3, PipelineV3]] = {}
    for snapshot in loaded_snapshots:
        snapshot_relative = snapshot.path.relative_to(root).as_posix()
        for pipeline in snapshot.pipelines.values():
            declared[(snapshot_relative, pipeline.id)] = (snapshot, pipeline)

    test_paths: list[Path] = []
    for suffix in ("*.mlir", "*.test"):
        for path in root.rglob(suffix):
            if not path.is_file():
                continue
            relative_parts = path.relative_to(root).parts
            if any(part.startswith(".") for part in relative_parts):
                continue
            if relative_parts and relative_parts[0] in {"build", "_build"}:
                continue
            test_paths.append(path)
    test_paths = sorted(set(test_paths))

    run_bindings: list[RunBinding] = []
    finalizers: list[FinalizerBinding] = []
    dispatches: list[DispatchBinding] = []
    actual_requires: dict[str, set[str]] = {}
    for test_path in test_paths:
        bindings, test_finalizers, test_dispatches, requires = _scan_test(root, test_path)
        relative = test_path.relative_to(root).as_posix()
        run_bindings.extend(bindings)
        finalizers.extend(test_finalizers)
        dispatches.extend(test_dispatches)
        actual_requires[relative] = requires

    dispatch_by_pipeline: dict[str, list[DispatchBinding]] = {}
    for dispatch in dispatches:
        owners = dispatch_by_pipeline.setdefault(dispatch.pipeline, [])
        if any(owner.test == dispatch.test for owner in owners):
            previous = next(owner for owner in owners if owner.test == dispatch.test)
            raise CheckpointError(
                f"{dispatch.test}:{dispatch.line}: duplicate checkpoint dispatcher; "
                f"first at {previous.test}:{previous.line}"
            )
        if not any(pipeline_id == dispatch.pipeline for _, pipeline_id in declared):
            raise CheckpointError(
                f"{dispatch.test}:{dispatch.line}: checkpoint dispatcher owns no declared "
                f"pipeline named {dispatch.pipeline!r}"
            )
        owners.append(dispatch)

    direct: dict[tuple[str, str], RunBinding] = {}
    for binding in run_bindings:
        key = (binding.snapshot, binding.pipeline)
        if key not in declared:
            raise CheckpointError(
                f"{binding.test}:{binding.line}: RUN binding references undeclared pipeline "
                f"{binding.snapshot}#{binding.pipeline}"
            )
        if key in direct:
            previous = direct[key]
            raise CheckpointError(
                f"{binding.test}:{binding.line}: duplicate RUN binding; first at "
                f"{previous.test}:{previous.line}"
            )
        direct[key] = binding
        _, pipeline = declared[key]
        expected_mode = "check-existing" if pipeline.kind == "bytes" else "run"
        if binding.mode != expected_mode:
            raise CheckpointError(
                f"{binding.test}:{binding.line}: {pipeline.kind} requires {expected_mode}"
            )

    owners: dict[tuple[str, str], RunBinding] = dict(direct)
    for key in sorted(set(declared) - set(direct)):
        snapshot_relative, pipeline_id = key
        candidates = dispatch_by_pipeline.get(pipeline_id, [])
        if len(candidates) != 1:
            if not candidates:
                raise CheckpointError(
                    f"missing RUN binding: {snapshot_relative}#{pipeline_id}"
                )
            labels = [f"{item.test}:{item.line}" for item in candidates]
            raise CheckpointError(
                f"ambiguous dispatch binding for {snapshot_relative}#{pipeline_id}: "
                + ", ".join(labels)
            )
        dispatch = candidates[0]
        synthetic = RunBinding(
            test=dispatch.test,
            mode="dispatch",
            snapshot=snapshot_relative,
            pipeline=pipeline_id,
            input_paths=(),
            producer_arguments=dispatch.producer_arguments,
            line=dispatch.line,
        )
        owners[key] = synthetic
        run_bindings.append(synthetic)

    # Attach lit-owned metadata to copies returned by Inventory.  Bare
    # load_snapshot remains a pure snapshot parse with no inferred execution
    # fields.
    enriched_snapshots: list[SnapshotV3] = []
    tests_with_pipelines: set[str] = set()
    for snapshot in loaded_snapshots:
        snapshot_relative = snapshot.path.relative_to(root).as_posix()
        enriched: dict[str, PipelineV3] = {}
        for identifier, pipeline in snapshot.pipelines.items():
            owner = owners[(snapshot_relative, identifier)]
            requires = tuple(sorted(actual_requires.get(owner.test, set())))
            enriched[identifier] = replace(
                pipeline, test=owner.test, requires=requires
            )
            tests_with_pipelines.add(owner.test)
        enriched_snapshots.append(replace(snapshot, pipelines=enriched))

    by_test: dict[str, list[FinalizerBinding]] = {}
    for finalizer in finalizers:
        if finalizer.declared_test != finalizer.test:
            raise CheckpointError(
                f"{finalizer.test}:{finalizer.line}: --test resolves to {finalizer.declared_test}"
            )
        by_test.setdefault(finalizer.test, []).append(finalizer)
    for test in sorted(tests_with_pipelines):
        owners = by_test.get(test, [])
        if len(owners) != 1:
            raise CheckpointError(f"{test}: expected exactly one checkpoint finalizer, got {len(owners)}")
    extras = sorted(set(by_test) - tests_with_pipelines)
    if extras:
        raise CheckpointError("finalizers without declared pipelines: " + ", ".join(extras))
    return Inventory(tuple(enriched_snapshots), tuple(run_bindings), tuple(finalizers))


def validate_inventory(root: Path) -> list[str]:
    """Return diagnostics for integration into aggregate harness validators."""

    try:
        build_inventory(root)
    except (CheckpointError, OSError) as error:
        return [str(error)]
    return []


def inventory_errors(root: Path) -> list[str]:
    return validate_inventory(root)


def manifest_field(value: Any, field: str) -> Any:
    """Resolve dotted fields while permitting dots inside actual JSON keys.

    At each object level the longest existing dotted prefix wins.  This makes
    ``candidate_sidecar_sha256.expected-report.json`` select the literal
    ``expected-report.json`` key without inventing a JSONPath language.
    """

    if not FIELD_PATH.fullmatch(field):
        raise CheckpointError(f"malformed manifest field path {field!r}")
    remaining = field
    current = value
    while remaining:
        if not isinstance(current, Mapping):
            raise CheckpointError(f"manifest field {field!r} crosses a non-object")
        if remaining in current:
            return current[remaining]
        splits = [index for index, char in enumerate(remaining) if char == "."]
        selected: tuple[str, str] | None = None
        for index in reversed(splits):
            candidate = remaining[:index]
            if candidate in current:
                selected = (candidate, remaining[index + 1 :])
                break
        if selected is None:
            raise CheckpointError(f"manifest has no field {field!r}")
        current = current[selected[0]]
        remaining = selected[1]
    return current


def verify_digest_binding(root: Path, path: str, binding: DigestBinding) -> str:
    artifact = resolve_root_path(root, path, "artifact path")
    manifest_path = resolve_root_path(root, binding.manifest, "digest manifest")
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise CheckpointError(f"duplicate manifest key {key!r}")
            result[key] = value
        return result

    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"), object_pairs_hook=pairs
        )
    except (OSError, json.JSONDecodeError) as error:
        raise CheckpointError(f"cannot read digest manifest {binding.manifest}: {error}") from error
    expected = manifest_field(manifest, binding.field)
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        raise CheckpointError(
            f"manifest field {binding.field!r} is not a lowercase SHA-256 digest"
        )
    actual = byte_digest(artifact.read_bytes())
    if actual != expected:
        raise CheckpointError(
            f"exact digest mismatch for {path}: expected {expected}, got {actual}"
        )
    return actual


def records_root(value: Path | None = None) -> Path:
    if value is not None:
        return Path(value).resolve()
    build_root = os.environ.get("LIT_BUILD_ROOT")
    if not build_root:
        raise CheckpointError("--records or LIT_BUILD_ROOT is required")
    return (Path(build_root).resolve() / "checkpoints")


def observation_path(records: Path, snapshot: SnapshotV3, pipeline: PipelineV3) -> Path:
    return records.resolve() / snapshot.case / f"{pipeline.id}.actual.yaml"


def pipelines_for_test(
    snapshots: Iterable[SnapshotV3], test: str
) -> tuple[tuple[SnapshotV3, PipelineV3], ...]:
    return tuple(
        (snapshot, pipeline)
        for snapshot in snapshots
        for pipeline in snapshot.pipelines.values()
        if pipeline.test == test
    )
