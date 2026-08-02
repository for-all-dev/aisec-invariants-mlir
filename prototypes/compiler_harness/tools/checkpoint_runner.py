#!/usr/bin/env python3
"""Execute and validate minimal Snapshot V3 pipeline checkpoints.

Snapshots describe expected evidence.  Lit owns execution, artifact paths,
capability gates, and ordering; this runner only binds a lit command to a
declared pipeline, records a nonauthoritative checkpoint observation, and
compares an optional final SPS report with the snapshot's expected axes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import yaml

import checkpoint_extractors
import checkpoint_model
import counterexample_pair


RUNNER_VERSION = "checkpoint-runner-v2"
RESULT_VIEW_FORMAT_ID = "SPS-Harness-Fixture-Final-Result-View-v2"
PASSED = "PassedV1"
FAILED = "FailedV1"
UNSUPPORTED = "UnsupportedV1"
BLOCKED = "BlockedByV1"
STATES = {PASSED, FAILED, UNSUPPORTED, BLOCKED}
ENDPOINT_TAGS = {
    "StructuralEndpointV1",
    "ExactBytesEndpointV1",
    "HarnessStageReportEndpointV1",
    "CanonicalSPSJsonEndpointV1",
    "ReferenceRelationEndpointV1",
}

STRUCTURAL_KINDS = {
    "mlir": ("mlir", "mlir-structure-v1"),
    "llvm-ir": ("llvm-ir", "llvm-ir-structure-v1"),
    "mir": ("mir", "mir-structure-v1"),
    "assembly": ("assembly", "assembly-structure-v1"),
    "object": ("object-inventory", "object-inventory-v1"),
}

FORBIDDEN_OBSERVATION_KEYS = {
    "modelstatus",
    "deploymentstatus",
    "deploymentresult",
    "policyreviewstatus",
    "policystatus",
    "productdisposition",
    "receipt",
    "receipts",
    "receiptid",
    "receiptids",
    "protectedreceipt",
    "protectedreceipts",
    "witness",
    "witnesses",
    "policydecision",
    "policydecisions",
    "claimable",
    "nfconforms",
    "hostname",
    "timestamp",
}
FORBIDDEN_RELATION_RESULT_KEYS = {
    "status",
    "disposition",
    "normativedisposition",
    "model",
    "models",
    "productsafe",
    "inputvalues",
    "trace",
    "traces",
    "witness",
    "witnesses",
}


class RunnerError(checkpoint_model.CheckpointError):
    pass


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def _atomic_write(path: Path, raw: bytes) -> None:
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


def _reject_observation_authority(value: Any, source: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = "".join(
                character for character in str(key).lower() if character.isalnum()
            )
            if normalized in FORBIDDEN_OBSERVATION_KEYS:
                raise RunnerError(f"{source}: forbidden authoritative field {key!r}")
            _reject_observation_authority(item, source)
    elif isinstance(value, list):
        for item in value:
            _reject_observation_authority(item, source)
    elif isinstance(value, str) and value.startswith("/"):
        raise RunnerError(f"{source}: absolute paths are forbidden")


def _reject_relation_result_authority(value: Any, source: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = "".join(
                character for character in str(key).lower() if character.isalnum()
            )
            if normalized in FORBIDDEN_RELATION_RESULT_KEYS:
                raise RunnerError(f"{source}: forbidden relation-result field {key!r}")
            _reject_relation_result_authority(item, source)
    elif isinstance(value, list):
        for item in value:
            _reject_relation_result_authority(item, source)


def _yaml_bytes(value: Mapping[str, Any]) -> bytes:
    _reject_observation_authority(value, "observation")
    rendered = yaml.dump(
        dict(value),
        Dumper=_NoAliasDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=1000,
    )
    checkpoint_model.strict_yaml_load(rendered.encode("utf-8"), source="observation")
    return rendered.encode("utf-8")


def _strict_json(raw: bytes, source: str) -> Any:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise RunnerError(f"{source}: UTF-8 BOM is forbidden")

    def pairs(rows: list[tuple[str, Any]]) -> OrderedDict[str, Any]:
        result: OrderedDict[str, Any] = OrderedDict()
        for key, value in rows:
            if key in result:
                raise RunnerError(f"{source}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def bad_float(_: str) -> Any:
        raise RunnerError(f"{source}: floating-point JSON numbers are forbidden")

    def bad_constant(value: str) -> Any:
        raise RunnerError(f"{source}: forbidden JSON constant {value}")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=bad_float,
            parse_constant=bad_constant,
        )
    except UnicodeDecodeError as error:
        raise RunnerError(f"{source}: invalid UTF-8") from error
    except json.JSONDecodeError as error:
        raise RunnerError(f"{source}: invalid JSON: {error}") from error


def _relative(root: Path, path: Path, description: str) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise RunnerError(f"{description} is outside its required root") from error


def _load_pipeline(
    root: Path, snapshot_argument: str, pipeline_id: str
) -> tuple[checkpoint_model.SnapshotV3, checkpoint_model.PipelineV3]:
    snapshot_path = Path(snapshot_argument)
    if not snapshot_path.is_absolute():
        snapshot_path = root / snapshot_path
    snapshot = checkpoint_model.load_snapshot(snapshot_path, root)
    try:
        return snapshot, snapshot.pipelines[pipeline_id]
    except KeyError as error:
        raise RunnerError(
            f"{snapshot.path}: no declared pipeline {pipeline_id!r}"
        ) from error


def _canonical_observation_root() -> Path:
    return checkpoint_model.records_root(None)


def _marker_path(
    records: Path,
    snapshot: checkpoint_model.SnapshotV3,
    pipeline: checkpoint_model.PipelineV3,
) -> Path:
    safe_case = snapshot.case.replace("/", "--")
    return records.resolve() / f"{safe_case}--{pipeline.id}.json"


def _write_marker(
    records: Path,
    snapshot: checkpoint_model.SnapshotV3,
    pipeline: checkpoint_model.PipelineV3,
    observation_raw: bytes,
) -> None:
    marker = {
        "format_id": "SPS-Harness-Pipeline-Endpoint-Marker-v1",
        "case": snapshot.case,
        "pipeline": pipeline.id,
        "observation_sha256": checkpoint_model.byte_digest(observation_raw),
    }
    _atomic_write(
        _marker_path(records, snapshot, pipeline), checkpoint_model.canonical_bytes(marker)
    )


def _endpoint_descriptor(
    snapshot: checkpoint_model.SnapshotV3,
    pipeline: checkpoint_model.PipelineV3,
) -> dict[str, str]:
    del snapshot
    if pipeline.kind in STRUCTURAL_KINDS:
        representation, extractor = STRUCTURAL_KINDS[pipeline.kind]
        return {
            "tag": "StructuralEndpointV1",
            "representation": representation,
            "extractor": extractor,
        }
    if pipeline.kind == "diagnostic":
        return {
            "tag": "HarnessStageReportEndpointV1",
            "extractor": "stage-report-json-v1",
        }
    if pipeline.kind == "json":
        return {
            "tag": "CanonicalSPSJsonEndpointV1",
            "extractor": pipeline.root_type or "strict-json-v1",
        }
    if pipeline.kind == "relation-reference":
        return {
            "tag": "ReferenceRelationEndpointV1",
            "extractor": "reference-relation-result-v1",
            "profile": pipeline.profile or "missing",
        }
    if pipeline.kind == "bytes":
        return {"tag": "ExactBytesEndpointV1", "extractor": "sha256"}
    raise RunnerError(f"pipeline {pipeline.id}: unsupported kind {pipeline.kind!r}")


def _producer(command: list[str]) -> dict[str, str]:
    if not command:
        return {
            "name": "checkpoint-runner",
            "version": RUNNER_VERSION,
            "build_sha256": checkpoint_model.byte_digest(Path(__file__).read_bytes()),
        }
    executable = shutil.which(command[0]) or command[0]
    executable_path = Path(executable)
    build_digest = (
        checkpoint_model.byte_digest(executable_path.read_bytes())
        if executable_path.is_file()
        else checkpoint_model.byte_digest(command[0].encode("utf-8"))
    )
    version = "unavailable"
    try:
        completed = subprocess.run(
            [executable, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=3,
            text=True,
        )
        first_line = completed.stdout.splitlines()[0].strip() if completed.stdout else ""
        if first_line:
            name = Path(command[0]).name
            version = first_line.replace(str(executable), name).replace(command[0], name)[:256]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {
        "name": Path(command[0]).name,
        "version": version,
        "build_sha256": build_digest,
    }


def _target_configuration(command: list[str]) -> dict[str, str]:
    prefixes = {
        "--target=": "triple",
        "-target=": "triple",
        "-mtriple=": "triple",
        "-march=": "architecture",
        "-mcpu=": "cpu",
        "-mabi=": "abi",
        "-mattr=": "features",
    }
    result: dict[str, str] = {}
    for token in command:
        for prefix, field in prefixes.items():
            if token.startswith(prefix):
                result[field] = token[len(prefix) :]
    return dict(sorted(result.items()))


def _observation(
    snapshot: checkpoint_model.SnapshotV3,
    pipeline: checkpoint_model.PipelineV3,
    *,
    state: str,
    command: list[str],
    producer: Mapping[str, str] | None = None,
    endpoint_sha256: str | None = None,
    facts: Mapping[str, Any] | None = None,
    payload: Mapping[str, Any] | None = None,
    failure: Mapping[str, Any] | None = None,
    blocked_by: list[str] | None = None,
) -> dict[str, Any]:
    if state not in STATES:
        raise RunnerError(f"invalid observation state {state}")
    result: dict[str, Any] = {
        "format_id": checkpoint_model.OBSERVATION_FORMAT_ID,
        "case": snapshot.case,
        "pipeline": pipeline.id,
        "endpoint": _endpoint_descriptor(snapshot, pipeline),
        "state": state,
        "inputs": [],
        "producer": dict(producer) if producer is not None else _producer(command),
        "invocation_sha256": checkpoint_model.canonical_digest(command),
        "target_configuration": _target_configuration(command),
    }
    if endpoint_sha256 is not None:
        result["endpoint_sha256"] = endpoint_sha256
    if facts is not None:
        result["facts"] = dict(facts)
    if payload is not None:
        result["payload"] = dict(payload)
    if failure is not None:
        result["failure"] = dict(failure)
    if blocked_by is not None:
        result["blocked_by"] = blocked_by
    return result


def _read_observation(raw: bytes, source: str) -> Mapping[str, Any]:
    value = checkpoint_model.strict_yaml_load(raw, source=source)
    _reject_observation_authority(value, source)
    required = {
        "format_id",
        "case",
        "pipeline",
        "endpoint",
        "state",
        "inputs",
        "producer",
        "invocation_sha256",
        "target_configuration",
    }
    allowed = required | {
        "endpoint_sha256",
        "facts",
        "payload",
        "failure",
        "blocked_by",
    }
    if not required <= set(value) or not set(value) <= allowed:
        raise RunnerError(f"{source}: observation has wrong fields")
    if value["format_id"] != checkpoint_model.OBSERVATION_FORMAT_ID:
        raise RunnerError(f"{source}: wrong observation format")
    if value["state"] not in STATES:
        raise RunnerError(f"{source}: unknown observation state")
    if value["inputs"] != []:
        raise RunnerError(f"{source}: minimal V3 observations must not carry inputs")
    if value["state"] == PASSED and "endpoint_sha256" not in value:
        raise RunnerError(f"{source}: passed observation lacks endpoint digest")
    if value["state"] == FAILED and "failure" not in value:
        raise RunnerError(f"{source}: failed observation lacks failure")
    if value["state"] == BLOCKED and "blocked_by" not in value:
        raise RunnerError(f"{source}: blocked observation lacks blocked_by")
    if value["state"] == PASSED and ({"failure", "blocked_by"} & set(value)):
        raise RunnerError(f"{source}: passed observation carries failure state")
    endpoint = value["endpoint"]
    valid_endpoint_fields = (
        {"tag", "extractor"},
        {"tag", "representation", "extractor"},
        {"tag", "extractor", "profile"},
    )
    if not isinstance(endpoint, Mapping) or set(endpoint) not in valid_endpoint_fields:
        raise RunnerError(f"{source}: malformed endpoint descriptor")
    if endpoint.get("tag") not in ENDPOINT_TAGS:
        raise RunnerError(f"{source}: unknown endpoint descriptor tag")
    if endpoint.get("tag") == "ReferenceRelationEndpointV1":
        if endpoint != {
            "tag": "ReferenceRelationEndpointV1",
            "extractor": "reference-relation-result-v1",
            "profile": checkpoint_model.RELATION_REFERENCE_PROFILE,
        }:
            raise RunnerError(f"{source}: malformed relation-reference endpoint")
    elif "profile" in endpoint:
        raise RunnerError(f"{source}: profile is legal only on a relation endpoint")
    producer = value["producer"]
    if not isinstance(producer, Mapping) or set(producer) != {
        "name",
        "version",
        "build_sha256",
    }:
        raise RunnerError(f"{source}: malformed producer descriptor")
    if not checkpoint_model.SHA256.fullmatch(str(producer["build_sha256"])):
        raise RunnerError(f"{source}: malformed producer build digest")
    if not checkpoint_model.SHA256.fullmatch(str(value["invocation_sha256"])):
        raise RunnerError(f"{source}: malformed invocation digest")
    if "endpoint_sha256" in value and not checkpoint_model.SHA256.fullmatch(
        str(value["endpoint_sha256"])
    ):
        raise RunnerError(f"{source}: malformed endpoint digest")
    if "facts" in value and not isinstance(value["facts"], Mapping):
        raise RunnerError(f"{source}: facts must be a mapping")
    if "payload" in value:
        payload = value["payload"]
        if not isinstance(payload, Mapping) or set(payload) != {"path", "sha256"}:
            raise RunnerError(f"{source}: malformed payload reference")
        if not checkpoint_model.SHA256.fullmatch(str(payload["sha256"])):
            raise RunnerError(f"{source}: malformed payload digest")
    if "failure" in value:
        failure = value["failure"]
        if (
            not isinstance(failure, Mapping)
            or not set(failure) <= {"kind", "exit_code", "details"}
            or "kind" not in failure
        ):
            raise RunnerError(f"{source}: malformed failure record")
    if "blocked_by" in value and (
        not isinstance(value["blocked_by"], list)
        or any(not isinstance(item, str) for item in value["blocked_by"])
        or value["blocked_by"] != sorted(set(value["blocked_by"]))
    ):
        raise RunnerError(f"{source}: malformed blocked_by list")
    target = value["target_configuration"]
    if not isinstance(target, Mapping) or not set(target) <= {
        "triple",
        "architecture",
        "cpu",
        "abi",
        "features",
    }:
        raise RunnerError(f"{source}: malformed target configuration")
    return value


def _write_observation(
    records: Path,
    snapshot: checkpoint_model.SnapshotV3,
    pipeline: checkpoint_model.PipelineV3,
    value: Mapping[str, Any],
) -> Path:
    raw = _yaml_bytes(value)
    observation = checkpoint_model.observation_path(
        _canonical_observation_root(), snapshot, pipeline
    )
    _atomic_write(observation, raw)
    _write_marker(records, snapshot, pipeline, raw)
    return observation


def _payload_reference(path: Path, raw: bytes) -> dict[str, str]:
    build_root_text = os.environ.get("LIT_BUILD_ROOT")
    if not build_root_text:
        raise RunnerError("LIT_BUILD_ROOT is required")
    return {
        "path": _relative(Path(build_root_text).resolve(), path, "payload"),
        "sha256": checkpoint_model.byte_digest(raw),
    }


def re_findall_scan_findings(text: str) -> list[str]:
    import re

    return re.findall(r"(?m)^\s*\[([a-z][a-z0-9-]*)\]", text)


def re_find_scan_summary(text: str) -> int:
    import re

    matches = re.findall(r"(?m)^\s*findings:\s*([0-9]+)\s*$", text)
    if len(matches) != 1:
        raise RunnerError("sps-scan output must contain exactly one findings summary")
    return int(matches[0])


def _normalize_stage_report(
    raw: bytes, pipeline: checkpoint_model.PipelineV3
) -> tuple[Mapping[str, Any], list[str]]:
    try:
        import check_sps_stage_report
    except ImportError as error:
        raise RunnerError("stage-report validator is unavailable") from error
    stage_id = pipeline.stage_id or pipeline.id
    try:
        value = _strict_json(raw, "stage-report endpoint")
        if not isinstance(value, Mapping) or value.get("formatId") != getattr(
            check_sps_stage_report, "FORMAT_ID", "SPS-Harness-Stage-Report-v2"
        ):
            raise RunnerError("not a stage-report JSON object")
    except RunnerError:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RunnerError("diagnostic output is not UTF-8") from error
        identifiers = re_findall_scan_findings(text)
        summary = re_find_scan_summary(text)
        if summary != len(identifiers):
            raise RunnerError(
                f"sps-scan findings summary {summary} disagrees with "
                f"{len(identifiers)} records"
            )
        counts: dict[str, int] = {}
        findings: list[str] = []
        for identifier in identifiers:
            counts[identifier] = counts.get(identifier, 0) + 1
            suffix = f".{counts[identifier]}" if counts[identifier] > 1 else ""
            findings.append(identifier + suffix)
        value = {
            "formatId": check_sps_stage_report.FORMAT_ID,
            "fixtureTier": {"tag": "CandidateOnly"},
            "stageId": stage_id,
            "completedChecks": [stage_id],
            "findings": sorted(findings),
            "blockers": [],
            "claimable": False,
            "modelStatus": {"tag": "NotComputed"},
        }
    try:
        check_sps_stage_report.validate_stage_report(value, source="checkpoint endpoint")
    except check_sps_stage_report.StageReportError as error:
        raise RunnerError(str(error)) from error
    if value["stageId"] != stage_id:
        raise RunnerError(
            f"checkpoint endpoint stageId {value['stageId']!r} does not match {stage_id!r}"
        )
    projected = {
        "completedChecks": list(value["completedChecks"]),
        "findings": list(value["findings"]),
        "blockers": list(value["blockers"]),
    }
    return value, checkpoint_extractors.match_properties(
        pipeline.properties, projected
    )


def _relation_reference_api() -> tuple[Path, Any, Any]:
    reference_root = (
        Path(__file__).resolve().parent.parent
        / "contracts"
        / "vendor"
        / "sps-reference-rev4"
        / "reference"
    )
    if not reference_root.is_dir():
        raise RunnerError(f"vendored SPS reference is unavailable: {reference_root}")
    reference_text = str(reference_root)
    if reference_text not in sys.path:
        sys.path.insert(0, reference_text)
    try:
        from sps_ref import canonical as reference_canonical
        from sps_ref import evidence as reference_evidence
    except ImportError as error:
        raise RunnerError(f"vendored relation-reference validator is unavailable: {error}") from error
    for module in (reference_canonical, reference_evidence):
        module_path = Path(module.__file__).resolve()
        try:
            module_path.relative_to(reference_root.resolve())
        except ValueError as error:
            raise RunnerError(
                f"relation-reference module escaped the vendored closure: {module_path}"
            ) from error
    return reference_root, reference_canonical, reference_evidence


def _validate_relation_reference(
    snapshot: checkpoint_model.SnapshotV3,
    pipeline: checkpoint_model.PipelineV3,
    raw: bytes,
) -> tuple[Mapping[str, Any], Mapping[str, Any], list[str]]:
    reference_root, canonical, evidence = _relation_reference_api()
    try:
        value = canonical.load_json_bytes(raw)
        canonical_raw = canonical.canonical_bytes(value)
    except Exception as error:
        raise RunnerError(f"invalid relation-reference JSON: {error}") from error
    if canonical_raw != raw:
        raise RunnerError("relation-reference endpoint is not canonical JSON")
    if not isinstance(value, Mapping):
        raise RunnerError("relation-reference endpoint must be a JSON object")
    _reject_observation_authority(value, "relation-reference endpoint")
    _reject_relation_result_authority(value, "relation-reference endpoint")

    fixture_path = snapshot.path.parent / "relation-reference" / "fixture.json"
    binding_path = snapshot.path.parent / "relation-reference" / "binding.json"
    try:
        fixture = evidence.validate_relation_fixture(
            canonical.load_json_bytes(fixture_path.read_bytes())
        )
        binding = evidence.validate_reduction_binding(
            canonical.load_json_bytes(binding_path.read_bytes()),
            fixture,
            binding_path=binding_path,
            fixture_path=fixture_path,
        )
    except Exception as error:
        raise RunnerError(
            f"relation-reference case binding validation failed: {error}"
        ) from error
    if binding.get("harnessCase") != snapshot.case:
        raise RunnerError("relation-reference binding names the wrong harness case")
    snapshot_rows = [
        row for row in binding.get("files", []) if row.get("role") == "snapshot"
    ]
    if len(snapshot_rows) != 1:
        raise RunnerError("relation-reference binding lacks one exact snapshot file role")
    bound_snapshot = (
        binding_path.resolve().parent.parent / snapshot_rows[0]["path"]
    ).resolve()
    if bound_snapshot != snapshot.path.resolve():
        raise RunnerError(
            "relation-reference snapshot file role does not bind the active snapshot"
        )
    try:
        selected_pair = counterexample_pair.load_fixture_pair(snapshot)
    except counterexample_pair.CounterexamplePairError as error:
        raise RunnerError(
            f"relation-reference counterexample pair differs from Snapshot V3: {error}"
        ) from error
    if (selected_pair is None) != (binding.get("counterexamplePair") is None):
        raise RunnerError(
            "relation-reference pair selection differs from the active snapshot status"
        )

    profile_path = reference_root / "profiles" / "reference-relation-v1.json"
    try:
        profile = canonical.load_json_bytes(profile_path.read_bytes())
        profile_digest = canonical.canonical_digest(profile)
        validated = evidence.validate_relation_result(
            value,
            profile_path,
            fixture=fixture,
            binding=binding,
            fixture_path=fixture_path,
            binding_path=binding_path,
        )
        projected = evidence.project_relation_result(validated)
    except Exception as error:
        raise RunnerError(f"relation-reference validation failed: {error}") from error
    if not isinstance(profile, Mapping) or not isinstance(validated, Mapping):
        raise RunnerError("relation-reference validator returned a non-object")
    if not isinstance(projected, Mapping):
        raise RunnerError("relation-reference projection returned a non-object")

    expected_profile = pipeline.profile or ""
    if profile.get("profileId") != expected_profile:
        raise RunnerError(
            f"relation-reference profile file has id {profile.get('profileId')!r}, "
            f"expected {expected_profile!r}"
        )
    profile_binding = validated.get("profileBinding")
    if not isinstance(profile_binding, Mapping):
        raise RunnerError("relation-reference result lacks profileBinding")
    if profile_binding.get("profileId") != expected_profile:
        raise RunnerError("relation-reference result binds the wrong profile id")
    if profile_binding.get("canonicalProfileDigest") != profile_digest:
        raise RunnerError("relation-reference result binds the wrong profile digest")

    fixture_binding = validated.get("fixtureBinding")
    reduction_binding = validated.get("reductionBinding")
    if not isinstance(fixture_binding, Mapping) or not isinstance(
        reduction_binding, Mapping
    ):
        raise RunnerError("relation-reference result lacks fixture bindings")
    if fixture_binding != {
        "caseId": fixture["caseId"],
        "canonicalFixtureDigest": canonical.canonical_digest(fixture),
    }:
        raise RunnerError("relation-reference result binds the wrong fixture")
    if reduction_binding != {
        "harnessCase": snapshot.case,
        "canonicalBindingDigest": canonical.canonical_digest(binding),
    }:
        raise RunnerError("relation-reference result binds the wrong reduction")
    if validated.get("programDigest") != canonical.canonical_digest(
        fixture["input"]["program"]
    ):
        raise RunnerError("relation-reference result binds the wrong program")
    coalition = fixture["input"]["coalition"]
    coalition_descriptor = {
        "coalitionId": coalition["id"],
        "principals": sorted(coalition["principals"]),
        "controlledHosts": sorted(coalition["controlledHosts"]),
    }
    if validated.get("coalitionDescriptorDigest") != canonical.canonical_digest(
        coalition_descriptor
    ):
        raise RunnerError("relation-reference result binds the wrong coalition")

    unknown = set(projected) - checkpoint_model.RELATION_REFERENCE_FACTS
    if unknown:
        raise RunnerError(
            f"relation-reference projection emitted unknown facts {sorted(unknown)}"
        )
    missing = checkpoint_model.REQUIRED_RELATION_REFERENCE_FACTS - set(projected)
    if missing:
        raise RunnerError(
            f"relation-reference projection omitted required facts {sorted(missing)}"
        )
    projection = dict(projected)
    _reject_observation_authority(projection, "relation-reference projection")

    payload_path = checkpoint_model.observation_path(
        _canonical_observation_root(), snapshot, pipeline
    ).with_suffix(".reference-result.json")
    _atomic_write(payload_path, canonical_raw)
    mismatches = checkpoint_extractors.match_properties(
        pipeline.properties, projection
    )
    return projection, _payload_reference(payload_path, canonical_raw), mismatches


def _validate_endpoint(
    snapshot: checkpoint_model.SnapshotV3,
    pipeline: checkpoint_model.PipelineV3,
    raw: bytes,
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None, list[str]]:
    if pipeline.kind in STRUCTURAL_KINDS:
        representation, extractor = STRUCTURAL_KINDS[pipeline.kind]
        scope = {"function": pipeline.function or snapshot.entry}
        facts = checkpoint_extractors.extract(
            representation, extractor, raw, scope
        )
        mismatches = checkpoint_extractors.match_properties(
            pipeline.properties, facts
        )
        projected = {
            fact: facts[fact] for fact in pipeline.properties if fact in facts
        }
        return projected, None, mismatches
    if pipeline.kind == "diagnostic":
        report, mismatches = _normalize_stage_report(raw, pipeline)
        payload_path = checkpoint_model.observation_path(
            _canonical_observation_root(), snapshot, pipeline
        ).with_suffix(".stage-report.json")
        payload_raw = checkpoint_model.canonical_bytes(report)
        _atomic_write(payload_path, payload_raw)
        return None, _payload_reference(payload_path, payload_raw), mismatches
    if pipeline.kind == "relation-reference":
        return _validate_relation_reference(snapshot, pipeline, raw)
    if pipeline.kind == "json":
        value = _strict_json(raw, "JSON endpoint")
        if pipeline.root_type:
            try:
                import sps_interfaces

                value = sps_interfaces.require_canonical(raw)
                registry = sps_interfaces.load_default_registry()
                registry.validate_root(value, pipeline.root_type)
                failures = registry.semantic_failures(value, pipeline.root_type)
            except (OSError, ValueError) as error:
                raise RunnerError(
                    f"canonical SPS JSON validation failed: {error}"
                ) from error
            if failures:
                raise RunnerError(
                    "canonical SPS JSON semantic validation failed: "
                    + ", ".join(failures)
                )
        if pipeline.properties:
            if not isinstance(value, Mapping):
                raise RunnerError("JSON properties require an object endpoint")
            mismatches = checkpoint_extractors.match_properties(
                pipeline.properties, value
            )
            projection = {
                fact: value[fact] for fact in pipeline.properties if fact in value
            }
            return projection, None, mismatches
        return None, None, []
    if pipeline.kind == "bytes":
        return None, None, []
    raise RunnerError(f"pipeline {pipeline.id}: unsupported kind {pipeline.kind!r}")


def _execute(endpoint_argument: str, command: list[str]) -> tuple[bytes, Path | None, int]:
    endpoint: Path | None = None
    if endpoint_argument != "-":
        endpoint = Path(endpoint_argument)
        if not endpoint.is_absolute():
            endpoint = Path.cwd() / endpoint
        build_root_text = os.environ.get("LIT_BUILD_ROOT")
        if not build_root_text:
            raise RunnerError("LIT_BUILD_ROOT is required for a file endpoint")
        _relative(Path(build_root_text).resolve(), endpoint, "producer endpoint")
        if endpoint.exists():
            if not endpoint.is_file():
                raise RunnerError("producer endpoint exists and is not a file")
            endpoint.unlink()
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return b"", None, 127
    if endpoint_argument == "-":
        return completed.stdout, None, completed.returncode
    assert endpoint is not None
    if completed.returncode != 0 or not endpoint.is_file():
        return b"", endpoint, completed.returncode if completed.returncode else 1
    return endpoint.read_bytes(), endpoint, 0


def _reject_input_arguments(values: list[str]) -> None:
    if values:
        raise RunnerError(
            "minimal Snapshot V3 has no pipeline input declarations; remove --input"
        )


def command_run(arguments: argparse.Namespace) -> int:
    root = arguments.root.resolve()
    snapshot, pipeline = _load_pipeline(root, arguments.snapshot, arguments.pipeline)
    if pipeline.kind == "bytes":
        raise RunnerError("bytes pipelines require check-existing mode")
    _reject_input_arguments(arguments.input)
    records = arguments.records.resolve()
    command = list(arguments.command)
    if not command or command[0] != "--":
        raise RunnerError("run requires a literal -- producer boundary")
    command = command[1:]
    if not command:
        raise RunnerError("run requires a producer command after --")
    producer = _producer(command)
    raw, _, returncode = _execute(arguments.endpoint, command)
    if returncode != 0:
        observation = _observation(
            snapshot,
            pipeline,
            state=FAILED,
            command=command,
            producer=producer,
            failure={"kind": "ProducerFailedV1", "exit_code": returncode},
        )
        path = _write_observation(records, snapshot, pipeline, observation)
        print(f"recorded producer failure {snapshot.case}#{pipeline.id}: {path}")
        return 0
    endpoint_digest = checkpoint_model.byte_digest(raw)
    try:
        facts, payload, mismatches = _validate_endpoint(snapshot, pipeline, raw)
    except (RunnerError, checkpoint_extractors.ExtractorError) as error:
        facts, payload, mismatches = None, None, [str(error)]
    observation = _observation(
        snapshot,
        pipeline,
        state=FAILED if mismatches else PASSED,
        command=command,
        producer=producer,
        endpoint_sha256=endpoint_digest,
        facts=facts,
        payload=payload,
        failure=(
            {"kind": "EndpointMismatchV1", "details": mismatches}
            if mismatches
            else None
        ),
    )
    path = _write_observation(records, snapshot, pipeline, observation)
    print(f"recorded {observation['state']} checkpoint {snapshot.case}#{pipeline.id}: {path}")
    return 0


def _checked_endpoint(root: Path, value: str) -> tuple[Path, str]:
    path = Path(value)
    if not path.is_absolute():
        cwd_candidate = Path.cwd() / path
        root_candidate = root / path
        path = cwd_candidate if cwd_candidate.exists() else root_candidate
    relative = _relative(root, path, "checked-in endpoint")
    if not path.is_file():
        raise RunnerError(f"checked-in endpoint does not exist: {relative}")
    return path.resolve(), relative


def command_check_existing(arguments: argparse.Namespace) -> int:
    root = arguments.root.resolve()
    snapshot, pipeline = _load_pipeline(root, arguments.snapshot, arguments.pipeline)
    if pipeline.kind != "bytes":
        raise RunnerError("check-existing mode is reserved for bytes pipelines")
    _reject_input_arguments(arguments.input)
    records = arguments.records.resolve()
    endpoint_path, endpoint_relative = _checked_endpoint(root, arguments.endpoint)
    raw = endpoint_path.read_bytes()
    endpoint_digest = checkpoint_model.byte_digest(raw)
    failures: list[str] = []
    if pipeline.kind == "bytes":
        if pipeline.digest is None:
            failures.append("bytes pipeline has no digest binding")
        else:
            try:
                checkpoint_model.verify_digest_binding(
                    root, endpoint_relative, pipeline.digest
                )
            except checkpoint_model.CheckpointError as error:
                failures.append(str(error))
    try:
        facts, payload, mismatches = _validate_endpoint(snapshot, pipeline, raw)
        failures.extend(mismatches)
    except (RunnerError, checkpoint_extractors.ExtractorError) as error:
        facts, payload = None, None
        failures.append(str(error))
    observation = _observation(
        snapshot,
        pipeline,
        state=FAILED if failures else PASSED,
        command=[],
        endpoint_sha256=endpoint_digest,
        facts=facts,
        payload=payload,
        failure=(
            {"kind": "EndpointMismatchV1", "details": failures}
            if failures
            else None
        ),
    )
    path = _write_observation(records, snapshot, pipeline, observation)
    print(f"recorded {observation['state']} checkpoint {snapshot.case}#{pipeline.id}: {path}")
    return 0


def _normalize_test_argument(root: Path, value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return _relative(root, path, "finalizer test")


def _verify_final_observation(
    observation: Mapping[str, Any],
    snapshot: checkpoint_model.SnapshotV3,
    pipeline: checkpoint_model.PipelineV3,
    source: str,
) -> None:
    if observation["endpoint"] != _endpoint_descriptor(snapshot, pipeline):
        raise RunnerError(
            f"{source}: endpoint descriptor disagrees with declared pipeline"
        )
    if observation["inputs"] != []:
        raise RunnerError(f"{source}: minimal V3 observations may not bind inputs")
    payload = observation.get("payload")
    if payload is None:
        return
    build_root_text = os.environ.get("LIT_BUILD_ROOT")
    if not build_root_text:
        raise RunnerError(f"{source}: LIT_BUILD_ROOT is required to verify payload")
    try:
        payload_path = checkpoint_model.resolve_root_path(
            Path(build_root_text).resolve(), payload["path"], f"{source}.payload.path"
        )
    except checkpoint_model.CheckpointError as error:
        raise RunnerError(str(error)) from error
    actual_digest = checkpoint_model.byte_digest(payload_path.read_bytes())
    if actual_digest != payload["sha256"]:
        raise RunnerError(
            f"{source}: payload digest mismatch; expected {payload['sha256']}, "
            f"got {actual_digest}"
        )


def command_finalize(arguments: argparse.Namespace) -> int:
    root = arguments.root.resolve()
    test = _normalize_test_argument(root, arguments.test)
    inventory = checkpoint_model.build_inventory(root)
    owned = checkpoint_model.pipelines_for_test(inventory.snapshots, test)
    if not owned:
        raise RunnerError(f"{test}: no declared checkpoint pipelines")
    records = arguments.records.resolve()
    observation_root = _canonical_observation_root()
    failures: list[str] = []
    for snapshot, pipeline in owned:
        marker_path = _marker_path(records, snapshot, pipeline)
        observation_path = checkpoint_model.observation_path(
            observation_root, snapshot, pipeline
        )
        label = f"{snapshot.case}#{pipeline.id}"
        if not marker_path.is_file():
            failures.append(f"{label}: missing current-test marker")
            continue
        if not observation_path.is_file():
            failures.append(f"{label}: missing observation")
            continue
        try:
            marker = _strict_json(marker_path.read_bytes(), str(marker_path))
            raw = observation_path.read_bytes()
            observation = _read_observation(raw, str(observation_path))
            if not isinstance(marker, Mapping) or (
                marker.get("case") != snapshot.case
                or marker.get("pipeline") != pipeline.id
                or marker.get("observation_sha256")
                != checkpoint_model.byte_digest(raw)
            ):
                raise RunnerError(f"{label}: stale or mismatched marker")
            _verify_final_observation(
                observation, snapshot, pipeline, str(observation_path)
            )
        except RunnerError as error:
            failures.append(f"{label}: {error}")
            continue
        if (
            observation.get("case") != snapshot.case
            or observation.get("pipeline") != pipeline.id
        ):
            failures.append(f"{label}: observation identity mismatch")
        elif observation["state"] != PASSED:
            failures.append(f"{label}: {observation['state']}")
    if failures:
        print("checkpoint finalization failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"finalized {len(owned)} checkpoint pipelines for {test}")
    return 0


def command_inspect(arguments: argparse.Namespace) -> int:
    root = arguments.root.resolve()
    snapshot, pipeline = _load_pipeline(root, arguments.snapshot, arguments.pipeline)
    endpoint_value = arguments.endpoint
    if endpoint_value == "-":
        raw = sys.stdin.buffer.read()
        endpoint_relative: str | None = None
    else:
        endpoint_path, endpoint_relative = _checked_endpoint(root, endpoint_value)
        raw = endpoint_path.read_bytes()
    facts, payload, mismatches = _validate_endpoint(snapshot, pipeline, raw)
    if pipeline.kind == "bytes":
        if endpoint_relative is None:
            mismatches.append("bytes inspection requires a checked-in file")
        elif pipeline.digest is None:
            mismatches.append("bytes pipeline has no digest binding")
        else:
            try:
                checkpoint_model.verify_digest_binding(
                    root, endpoint_relative, pipeline.digest
                )
            except checkpoint_model.CheckpointError as error:
                mismatches.append(str(error))
    value = {
        "case": snapshot.case,
        "pipeline": pipeline.id,
        "endpoint_sha256": checkpoint_model.byte_digest(raw),
        "facts": facts or {},
        "payload": payload or {},
        "mismatches": mismatches,
    }
    sys.stdout.buffer.write(_yaml_bytes(value))
    return 1 if mismatches else 0


def _event_projection(event: Any) -> dict[str, Any]:
    if is_dataclass(event):
        value = asdict(event)
    elif isinstance(event, Mapping):
        value = dict(event)
    else:
        value = {
            "kind": event.kind,
            "field": event.field,
            "id": getattr(event, "id", None),
            "first_bad": getattr(event, "first_bad", False),
        }
    return {key: item for key, item in value.items() if item not in (None, False)}


def _expected_final(snapshot: checkpoint_model.SnapshotV3) -> dict[str, Any]:
    final = snapshot.final
    value: dict[str, Any] = {
        "model": dict(final.model),
        "deployment": final.deployment,
        "policy": final.policy,
        "events": [_event_projection(event) for event in final.events],
        "because": final.because,
    }
    if final.reference is not None:
        value["reference"] = final.reference
    return value


def _actual_final(report: Mapping[str, Any]) -> dict[str, Any]:
    tag = report.get("tag")
    if tag != "CompletedV2":
        return {"report": str(tag)}
    public = report.get("report")
    if not isinstance(public, Mapping):
        raise RunnerError("CompletedV2 report has no public report object")
    model = public.get("modelStatus")
    deployment = public.get("deploymentStatus")
    policy = public.get("policyReviewStatus")
    if not all(isinstance(item, Mapping) for item in (model, deployment, policy)):
        raise RunnerError("CompletedV2 report lacks a terminal status axis")
    actual_model: dict[str, Any] = {"status": str(model["tag"])}
    if model.get("tag") == "Unknown":
        args = model.get("args")
        reasons = [
            str(row["reasonClassId"])
            for row in args
            if isinstance(row, Mapping) and "reasonClassId" in row
        ] if isinstance(args, list) else []
        if reasons:
            actual_model["reasons"] = reasons
    return {
        "model": actual_model,
        "deployment": str(deployment["tag"]),
        "policy": str(policy["tag"]),
    }


def _compare_final(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> list[str]:
    mismatches: list[str] = []
    expected_model = expected["model"]
    actual_model = actual.get("model")
    if not isinstance(actual_model, Mapping):
        return [f"report arm is not CompletedV2: {actual.get('report')!r}"]
    if actual_model.get("status") != expected_model.get("status"):
        mismatches.append(
            "model status: expected "
            f"{expected_model.get('status')!r}, got {actual_model.get('status')!r}"
        )
    expected_reason = expected_model.get("reason")
    if expected_reason is not None and expected_reason not in actual_model.get("reasons", []):
        mismatches.append(
            f"model reason: expected {expected_reason!r}, "
            f"got {actual_model.get('reasons', [])!r}"
        )
    for field in ("deployment", "policy"):
        if actual.get(field) != expected.get(field):
            mismatches.append(
                f"{field}: expected {expected.get(field)!r}, got {actual.get(field)!r}"
            )
    return mismatches


def _load_final_report(path: Path) -> Mapping[str, Any]:
    try:
        import sps_interfaces

        raw = path.read_bytes()
        report = sps_interfaces.require_canonical(raw)
        registry = sps_interfaces.load_default_registry()
        registry.validate_root(report, "SPSRunReportV2")
        failures = registry.semantic_failures(report, "SPSRunReportV2")
    except (OSError, ValueError) as error:
        raise RunnerError(f"invalid SPSRunReportV2: {error}") from error
    if failures:
        raise RunnerError(
            "SPSRunReportV2 semantic validation failed: " + ", ".join(failures)
        )
    if not isinstance(report, Mapping):
        raise RunnerError("SPSRunReportV2 must be an object")
    return report


def command_check_final(arguments: argparse.Namespace) -> int:
    root = arguments.root.resolve()
    snapshot_path = Path(arguments.snapshot)
    if not snapshot_path.is_absolute():
        snapshot_path = root / snapshot_path
    snapshot = checkpoint_model.load_snapshot(snapshot_path, root)
    report_path = Path(arguments.report)
    if not report_path.is_absolute():
        report_path = Path.cwd() / report_path
    report = _load_final_report(report_path)
    if arguments.bundle is not None:
        try:
            import check_sps_v2_bundle

            check_sps_v2_bundle.check_bundle(Path(arguments.bundle).resolve(), report_path)
        except (OSError, ValueError) as error:
            raise RunnerError(f"SPS V2 bundle validation failed: {error}") from error
    expected = _expected_final(snapshot)
    actual = _actual_final(report)
    mismatches = _compare_final(expected, actual)
    value = {
        "case": snapshot.case,
        "expected_final": expected,
        "actual_final": actual,
        "comparison": "Mismatched" if mismatches else "Matched",
        "mismatches": mismatches,
    }
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 1 if mismatches else 0


def _checkpoint_result(snapshot: checkpoint_model.SnapshotV3) -> str:
    try:
        observation_root = _canonical_observation_root()
    except checkpoint_model.CheckpointError:
        return "NotObserved"
    states: list[str] = []
    for pipeline in snapshot.pipelines.values():
        path = checkpoint_model.observation_path(observation_root, snapshot, pipeline)
        if not path.is_file():
            continue
        try:
            observation = _read_observation(path.read_bytes(), str(path))
            if observation.get("case") != snapshot.case or observation.get("pipeline") != pipeline.id:
                return "InvalidObservation"
            states.append(str(observation["state"]))
        except (RunnerError, OSError):
            return "InvalidObservation"
    if not states:
        return "NotObserved"
    if len(states) != len(snapshot.pipelines):
        return "PartiallyObserved"
    return PASSED if all(state == PASSED for state in states) else FAILED


def command_results(arguments: argparse.Namespace) -> int:
    inventory = checkpoint_model.build_inventory(arguments.root.resolve())
    results = [
        {
            "case": snapshot.case,
            "expected_final": _expected_final(snapshot),
            "actual_final": None,
            "comparison": "NotCompared",
            "checkpoint_result": _checkpoint_result(snapshot),
        }
        for snapshot in inventory.snapshots
    ]
    counts = {"Proved": 0, "Counterexample": 0, "Unknown": 0}
    for row in results:
        status = row["expected_final"]["model"]["status"]
        counts[status] = counts.get(status, 0) + 1
    summary = {
        "fixtures": len(results),
        "expected_proved": counts["Proved"],
        "expected_counterexample": counts["Counterexample"],
        "expected_unknown": counts["Unknown"],
        "compared": 0,
    }
    view = {
        "format_id": RESULT_VIEW_FORMAT_ID,
        "results": results,
        "summary": summary,
    }
    if arguments.json:
        print(json.dumps(view, ensure_ascii=False, indent=2))
        return 0
    headings = (
        "CASE",
        "EXPECTED_MODEL",
        "EXPECTED_DEPLOYMENT",
        "EXPECTED_POLICY",
        "EVENTS",
        "ACTUAL_MODEL",
        "COMPARISON",
        "CHECKPOINT",
    )
    rows = []
    for row in results:
        expected = row["expected_final"]
        model = expected["model"]
        model_label = str(model["status"])
        qualifier = model.get("reason") or model.get("bad_state")
        if qualifier:
            model_label += f"({qualifier})"
        rows.append(
            (
                row["case"],
                model_label,
                str(expected["deployment"]),
                str(expected["policy"]),
                str(len(expected["events"])),
                "-",
                row["comparison"],
                row["checkpoint_result"],
            )
        )
    widths = [
        max(len(headings[index]), *(len(row[index]) for row in rows))
        for index in range(len(headings))
    ]
    print("  ".join(value.ljust(widths[index]) for index, value in enumerate(headings)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    print()
    print("Expected final axes are fixture contracts, independent of checkpoint execution.")
    print("Actual axes appear only when check-final validates a supplied SPSRunReportV2.")
    print(
        "summary: "
        f"fixtures={summary['fixtures']} "
        f"expected-proved={summary['expected_proved']} "
        f"expected-counterexample={summary['expected_counterexample']} "
        f"expected-unknown={summary['expected_unknown']}"
    )
    return 0


def command_inventory(arguments: argparse.Namespace) -> int:
    inventory = checkpoint_model.build_inventory(arguments.root.resolve())
    candidate_references = 0
    counts = {"Proved": 0, "Counterexample": 0, "Unknown": 0}
    for snapshot in inventory.snapshots:
        counts[snapshot.final.status] += 1
        candidate_references += int(snapshot.final.reference is not None)
        print(
            f"{snapshot.case}: final={snapshot.final.status}/"
            f"{snapshot.final.deployment}/{snapshot.final.policy} "
            f"events={len(snapshot.final.events)} "
            f"reference={snapshot.final.reference or '-'}"
        )
        for pipeline in snapshot.pipelines.values():
            requires = ",".join(pipeline.requires) if pipeline.requires else "-"
            print(
                f"  {pipeline.id}: kind={pipeline.kind} "
                f"test={pipeline.test or '-'} requires={requires}"
            )
    print(
        f"checkpoint inventory passed: {len(inventory.snapshots)} snapshots, "
        f"{sum(len(item.pipelines) for item in inventory.snapshots)} pipelines, "
        f"{len(inventory.run_bindings)} RUN bindings, "
        f"{len(inventory.finalizers)} finalizers, "
        f"{candidate_references} candidate references, "
        f"expected Proved/Counterexample/Unknown="
        f"{counts['Proved']}/{counts['Counterexample']}/{counts['Unknown']}"
    )
    return 0


def _common_binding(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--pipeline", required=True)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--input", action="append", default=[])


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    run = subparsers.add_parser("run")
    _common_binding(run)
    run.add_argument("--endpoint", required=True)
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(handler=command_run)

    existing = subparsers.add_parser("check-existing")
    _common_binding(existing)
    existing.add_argument("--endpoint", required=True)
    existing.set_defaults(handler=command_check_existing)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    finalize.add_argument("--test", required=True)
    finalize.add_argument("--records", required=True, type=Path)
    finalize.set_defaults(handler=command_finalize)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    inspect.add_argument("--snapshot", required=True)
    inspect.add_argument("--pipeline", required=True)
    inspect.add_argument("--endpoint", required=True)
    inspect.set_defaults(handler=command_inspect)

    inventory = subparsers.add_parser("inventory")
    inventory.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    inventory.set_defaults(handler=command_inventory)

    results = subparsers.add_parser("results")
    results.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    results.add_argument("--json", action="store_true")
    results.set_defaults(handler=command_results)

    check_final = subparsers.add_parser("check-final")
    check_final.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    check_final.add_argument("--snapshot", required=True)
    check_final.add_argument("--report", required=True)
    check_final.add_argument("--bundle")
    check_final.set_defaults(handler=command_check_final)
    return parser


def main() -> int:
    arguments = argument_parser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except (
        checkpoint_model.CheckpointError,
        checkpoint_extractors.ExtractorError,
        OSError,
    ) as error:
        print(f"checkpoint error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
