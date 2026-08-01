#!/usr/bin/env python3
"""Validate the materialized-file boundary for an SPS Rev4.1 V2 run.

This is a packaging and cross-file binding check.  It consumes the SPS-owned
vendored registry and its semantic validators; it does not execute the SPS
verifier, establish WFInputs or NFConforms, or authenticate a reported
ModelStatus.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sps_interfaces


BUNDLE_ROOTS = {
    "artifact-identity.sps.json": "ArtifactIdentityV2",
    "identity-evidence.sps.json": "ArtifactIdentityEvidenceV2",
    "sps-manifest.sps.json": "SPSLLVMNFManifestV2",
    "proof-configuration.sps.json": "ProofConfigurationV2",
    "aggregation-input.sps.json": "AggregationInputV2",
}


class BoundaryError(ValueError):
    """A materialized bundle does not satisfy the harness boundary contract."""


@dataclass(frozen=True)
class LoadedInterface:
    value: dict[str, Any]
    raw: bytes


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact_digest(value: object) -> str:
    return digest(sps_interfaces.canonical_bytes(value))


def require_registry_surface(registry: sps_interfaces.Registry) -> None:
    missing: list[str] = []
    required_members = (
        ("ArtifactIdentityV2", "canonicalBitcodeHash"),
        ("ArtifactIdentityV2", "proofConfigurationDigest"),
        ("ArtifactIdentityV2", "queryScheduleDerivationDigest"),
        ("ArtifactIdentityEvidenceV2", "artifactIdentityDigest"),
        ("ArtifactIdentityEvidenceV2", "artifactIdentity"),
        ("ArtifactIdentityEvidenceV2", "canonicalBitcode"),
        ("ArtifactIdentityEvidenceV2", "proofConfiguration"),
        ("ArtifactIdentityEvidenceV2", "queryScheduleDerivation"),
        ("SPSLLVMNFManifestV2", "artifactIdentity"),
        ("SPSLLVMNFManifestV2", "artifactIdentityEvidence"),
        ("ProofConfigurationV2", "requiredQuerySchedule"),
        ("AggregationInputV2", "artifactIdentityDigest"),
        ("AggregationInputV2", "proofConfigurationDigest"),
        ("AggregationInputV2", "queryScheduleDigest"),
        ("SPSPublicReportV2", "querySchedule"),
        ("SPSPublicReportV2", "queryScheduleDigest"),
        ("AggregationDecisionV2", "formatId"),
        ("AggregationDecisionV2", "identityEvidence"),
        ("AggregationDecisionV2", "input"),
        ("AggregationDecisionV2", "runReport"),
    )
    available_records: dict[str, set[str]] = {}
    for record, field in required_members:
        if record in available_records:
            available = available_records[record]
        else:
            try:
                available = set(registry.record_fields(record))
            except sps_interfaces.InterfaceError:
                missing.append(record)
                available = set()
            available_records[record] = available
        if available and field not in available:
            missing.append(f"{record}.{field}")
    try:
        report_variants = set(registry.union_variants("SPSRunReportV2"))
    except sps_interfaces.InterfaceError:
        missing.append("SPSRunReportV2")
    else:
        if "CompletedV2" not in report_variants:
            missing.append("SPSRunReportV2.CompletedV2")
    if missing:
        raise BoundaryError(
            "vendored SPS registry lacks the Rev4.1 V2 materialized boundary: "
            + "; ".join(dict.fromkeys(missing))
        )


def construct_registry_record(
    registry: sps_interfaces.Registry,
    record: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    try:
        fields = registry.record_fields(record)
    except sps_interfaces.InterfaceError as error:
        raise BoundaryError(f"vendored registry has no {record}") from error
    missing = [field for field in fields if field not in values]
    extra = [field for field in values if field not in fields]
    if missing or extra:
        raise BoundaryError(
            f"cannot construct vendored {record}: missing={missing}, extra={extra}"
        )
    return {field: values[field] for field in fields}


def referenced_record(
    registry: sps_interfaces.Registry, owner: str, field: str
) -> str:
    try:
        rows = registry.records[owner]["fields"]
        descriptor = next(row["type"] for row in rows if row["name"] == field)
    except (KeyError, StopIteration, TypeError) as error:
        raise BoundaryError(f"vendored registry has no {owner}.{field} binding") from error
    if descriptor.get("kind") != "record" or not isinstance(descriptor.get("name"), str):
        raise BoundaryError(f"vendored {owner}.{field} is not a named record")
    return descriptor["name"]


def load_interface(
    path: Path, root_type: str, registry: sps_interfaces.Registry
) -> LoadedInterface:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise BoundaryError(f"cannot read {path}: {error}") from error
    try:
        value = sps_interfaces.require_canonical(raw)
        registry.validate_root(value, root_type)
    except sps_interfaces.InterfaceError as error:
        raise BoundaryError(f"{path.name}: {error}") from error
    if not isinstance(value, dict):
        raise BoundaryError(f"{path.name}: interface root must be an object")
    semantic_failures = registry.semantic_failures(value, root_type)
    if semantic_failures:
        raise BoundaryError(
            f"{path.name}: semantic validation failed: "
            + ", ".join(semantic_failures)
        )
    return LoadedInterface(value=dict(value), raw=raw)


def require_equal(actual: object, expected: object, description: str) -> None:
    if actual != expected:
        raise BoundaryError(description)


def derived_public_schedule(
    registry: sps_interfaces.Registry,
    *,
    schedule_record: str,
    artifact_identity_digest: str,
    proof_configuration_digest: str,
    proof_configuration: dict[str, Any],
) -> dict[str, Any]:
    try:
        format_id = registry.value["formatLiterals"][schedule_record]
        queries = proof_configuration["requiredQuerySchedule"]["queries"]
    except (KeyError, TypeError) as error:
        raise BoundaryError("proof configuration has no required query schedule") from error
    schedule = construct_registry_record(
        registry,
        schedule_record,
        {
            "formatId": format_id,
            "artifactIdentityDigest": artifact_identity_digest,
            "proofConfigurationDigest": proof_configuration_digest,
            "queries": queries,
        },
    )
    try:
        registry.validate_root(schedule, schedule_record)
    except sps_interfaces.InterfaceError as error:
        raise BoundaryError(f"derived public query schedule is invalid: {error}") from error
    failures = registry.semantic_failures(schedule, schedule_record)
    if failures:
        raise BoundaryError(
            "derived public query schedule failed semantic validation: "
            + ", ".join(failures)
        )
    return schedule


def check_bundle(bundle: Path, report_path: Path) -> None:
    if not bundle.is_dir():
        raise BoundaryError(f"bundle directory does not exist: {bundle}")
    artifact_path = bundle / "artifact.bc"
    required_paths = [artifact_path, *(bundle / name for name in BUNDLE_ROOTS)]
    for path in required_paths:
        if not path.is_file():
            raise BoundaryError(f"missing required bundle member: {path.name}")
    if not report_path.is_file():
        raise BoundaryError(f"report does not exist: {report_path}")

    registry = sps_interfaces.load_default_registry()
    require_registry_surface(registry)
    schedule_record = referenced_record(registry, "SPSPublicReportV2", "querySchedule")
    if schedule_record != "PublicQueryScheduleV2":
        raise BoundaryError(
            "vendored SPSPublicReportV2.querySchedule does not reference "
            "PublicQueryScheduleV2"
        )

    loaded = {
        name: load_interface(bundle / name, root_type, registry)
        for name, root_type in BUNDLE_ROOTS.items()
    }
    report = load_interface(report_path, "SPSRunReportV2", registry)

    identity_loaded = loaded["artifact-identity.sps.json"]
    evidence_loaded = loaded["identity-evidence.sps.json"]
    manifest_loaded = loaded["sps-manifest.sps.json"]
    proof_loaded = loaded["proof-configuration.sps.json"]
    aggregation_loaded = loaded["aggregation-input.sps.json"]
    identity = identity_loaded.value
    evidence = evidence_loaded.value
    manifest = manifest_loaded.value
    proof = proof_loaded.value
    aggregation = aggregation_loaded.value

    require_equal(
        evidence["artifactIdentity"],
        identity,
        "identity-evidence.sps.json artifactIdentity does not equal artifact-identity.sps.json",
    )
    require_equal(
        manifest["artifactIdentity"],
        identity,
        "sps-manifest.sps.json artifactIdentity does not equal artifact-identity.sps.json",
    )
    require_equal(
        manifest["artifactIdentityEvidence"],
        evidence,
        "sps-manifest.sps.json artifactIdentityEvidence does not equal identity-evidence.sps.json",
    )
    require_equal(
        evidence["proofConfiguration"],
        proof,
        "identity-evidence.sps.json proofConfiguration does not equal proof-configuration.sps.json",
    )

    identity_digest = digest(identity_loaded.raw)
    proof_digest = digest(proof_loaded.raw)
    require_equal(
        evidence["artifactIdentityDigest"],
        identity_digest,
        "identity evidence artifactIdentityDigest does not hash artifact-identity.sps.json",
    )
    require_equal(
        identity["proofConfigurationDigest"],
        proof_digest,
        "artifact identity proofConfigurationDigest does not hash proof-configuration.sps.json",
    )

    try:
        artifact_raw = artifact_path.read_bytes()
    except OSError as error:
        raise BoundaryError(f"cannot read {artifact_path}: {error}") from error
    bitcode = evidence["canonicalBitcode"]
    try:
        evidence_bytes = bytes.fromhex(bitcode["exactBytes"])
    except (KeyError, TypeError, ValueError) as error:
        raise BoundaryError("identity evidence contains invalid canonical bitcode bytes") from error
    if artifact_raw != evidence_bytes:
        raise BoundaryError(
            "artifact.bc bytes differ from identity evidence canonicalBitcode.exactBytes"
        )
    artifact_digest = digest(artifact_raw)
    require_equal(
        bitcode["sha256"],
        artifact_digest,
        "canonical bitcode sha256 does not hash artifact.bc",
    )
    require_equal(
        identity["canonicalBitcodeHash"],
        artifact_digest,
        "artifact identity canonicalBitcodeHash does not hash artifact.bc",
    )

    derivation = evidence["queryScheduleDerivation"]
    require_equal(
        identity["queryScheduleDerivationDigest"],
        exact_digest(derivation),
        "artifact identity queryScheduleDerivationDigest does not hash identity evidence",
    )
    require_equal(
        derivation["requiredQuerySchedule"],
        proof["requiredQuerySchedule"],
        "query schedule derivation does not bind the proof configuration schedule",
    )
    for field in (
        "policyDigest",
        "abiDigest",
        "releaseDigest",
        "contractDigest",
        "entryScopeDigest",
        "profileConfigurationDigest",
    ):
        require_equal(
            derivation[field],
            identity[field],
            f"query schedule derivation {field} does not bind the artifact identity",
        )

    for field in (
        "releaseMarkerBindingsDigest",
        "releaseMarkerMachineMapDigest",
        "intrinsicDefinitionDigest",
        "aggregationSemanticsDigest",
        "replayAcceptanceSemanticsDigest",
    ):
        require_equal(
            manifest[field],
            identity[field],
            f"SPS manifest {field} does not bind the artifact identity",
        )
    for field in ("aggregationSemanticsDigest", "replayAcceptanceSemanticsDigest"):
        require_equal(
            proof[field],
            identity[field],
            f"proof configuration {field} does not bind the artifact identity",
        )

    require_equal(
        aggregation["artifactIdentityDigest"],
        identity_digest,
        "aggregation input artifactIdentityDigest does not bind the artifact identity",
    )
    require_equal(
        aggregation["proofConfigurationDigest"],
        proof_digest,
        "aggregation input proofConfigurationDigest does not bind the proof configuration",
    )
    schedule = derived_public_schedule(
        registry,
        schedule_record=schedule_record,
        artifact_identity_digest=identity_digest,
        proof_configuration_digest=proof_digest,
        proof_configuration=proof,
    )
    schedule_digest = exact_digest(schedule)
    require_equal(
        aggregation["queryScheduleDigest"],
        schedule_digest,
        "aggregation input queryScheduleDigest does not bind the required query schedule",
    )

    if report.value["tag"] == "CompletedV2":
        public_report = report.value["report"]
        require_equal(
            public_report["artifactIdentityDigest"],
            identity_digest,
            "completed report artifactIdentityDigest does not bind the artifact identity",
        )
        require_equal(
            public_report["proofConfigurationDigest"],
            proof_digest,
            "completed report proofConfigurationDigest does not bind the proof configuration",
        )
        require_equal(
            public_report["querySchedule"],
            schedule,
            "completed report querySchedule does not equal the required query schedule",
        )
        require_equal(
            public_report["queryScheduleDigest"],
            schedule_digest,
            "completed report queryScheduleDigest does not hash its query schedule",
        )

    try:
        decision_format = registry.value["formatLiterals"]["AggregationDecisionV2"]
    except (KeyError, TypeError) as error:
        raise BoundaryError("vendored AggregationDecisionV2 format literal is missing") from error
    decision = construct_registry_record(
        registry,
        "AggregationDecisionV2",
        {
            "formatId": decision_format,
            "identityEvidence": evidence,
            "input": aggregation,
            "runReport": report.value,
        },
    )
    try:
        registry.validate_root(decision, "AggregationDecisionV2")
    except sps_interfaces.InterfaceError as error:
        raise BoundaryError(f"constructed aggregation decision is invalid: {error}") from error
    failures = registry.semantic_failures(decision, "AggregationDecisionV2")
    if failures:
        raise BoundaryError(
            "constructed aggregation decision semantic validation failed: "
            + ", ".join(failures)
        )

    print(
        "validated SPS Rev4.1 V2 materialized bundle/report boundary; "
        "verifier not executed"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        check_bundle(arguments.bundle.resolve(), arguments.report.resolve())
    except (BoundaryError, sps_interfaces.InterfaceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
