#!/usr/bin/env python3
"""Build and validate the SPS Rev4.1 interface package with stdlib only.

The Python model below is the single source for the JSON Schemas and the
machine registry.  ``--write`` materializes readable source schemas and a
canonical, digest-locked distribution.  The default mode checks that every
tracked output is exactly reproducible.  ``--check-dist`` validates a copied
distribution without consulting repository-relative paths.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_SET_ID = "SPS-Interfaces-Rev4.1-2026-08-01"
SOURCE_REVISION = "SPS-Rev4.1-V2-2026-08-01"
BASE_ID = "https://sps.dev/interfaces/rev4.1/"
BUNDLE_ID = BASE_ID + "schemas/sps-rev4.1.bundle.schema.json"

QUERY_KINDS = [
    "AuditAll", "ReleaseConformance", "AdmissionNonempty", "HighVariation",
    "ReleaseActivation", "LLVMDefinedness", "Initialization",
    "BoundAdequacy", "StructuralAlloca", "OutputClosure", "CouplingTotality",
    "CouplingFiberTotal", "CouplingSymmetry", "CouplingSchedulePreservation",
]

PUBLIC_REASONS_V2 = [
    "AliasBindingMismatch", "AllocaSizeNotWorldStructural", "ArtifactMismatch",
    "ContractAllocationUnsupported", "ContractReleaseUnsupported",
    "CouplingFiberCoverageFailure", "DiagnosticHealthFailure",
    "ExpectedHighVariationAbsent", "FreezeMayChoose",
    "HorizonDerivationMismatch", "HorizonDerivationUnsupported", "IndirectCall",
    "InvalidDiagnosticShortcut", "LayoutDependentPointerComparison",
    "LoopRemainder", "ManifestMismatch", "MechanismNondeterminismUnsupported",
    "NormalizerMismatch", "OpenModelObligations", "OutputBindingIncomplete",
    "OutputBindingOverlap", "OutputClosureMismatch",
    "PONFFPArithmeticUnsupported", "PONFIntrinsicUnsupported",
    "PersistentInvariantEncodingUnsupported", "PipelineMismatch",
    "PlacementMismatch", "PoisonSemanticsUnsupported", "PossibleUB",
    "PublicBoundBindingMismatch", "Recursion", "ReleaseActivationMismatch",
    "ReleaseCarrierMismatch", "ReleaseConformanceUnknown", "ResidualVector", "ResourceLimit",
    "SolverTimeout", "StableIdentityMismatch", "ToolInconsistency",
    "UnclassifiedAnnotation", "UnclassifiedIR",
    "UninitializedLoadProducesUndef", "UninitializedOutputByte",
    "UnsupportedAddressObservationProfile", "UnsupportedOpcode",
    "UnsupportedStackProtector", "UnsupportedType", "VacuousAdmission",
]

LINT_CLASSES = [
    "IdentityReleaseOfHigh", "WorldAudienceContributionOverThreshold",
    "ExpectedVariableDeclaredWorldVisible", "CoalitionEntryTotalOverThreshold",
]

CONFIG_REASONS_V2 = [
    "NoncanonicalInterface", "MissingRequiredIdentity",
    "UnsupportedInterfaceVersion", "InterfaceDigestMismatch",
    "ArtifactParseFailure", "InsufficientEvidenceCapacity",
]
REPORT_FAILURES_V2 = ["RestrictedStoreUnavailable", "EvidenceFinalizationFailure"]
BLOCKER_SCOPES_V2 = ["ReplayInvalidating", "ProofCompletion", "RunFinalization"]


def scalar(kind: str) -> dict[str, Any]:
    return {"kind": kind}


def literal(value: Any) -> dict[str, Any]:
    return {"kind": "literal", "value": value}


def enum(name: str) -> dict[str, Any]:
    return {"kind": "enum", "name": name}


def record(name: str) -> dict[str, Any]:
    return {"kind": "record", "name": name}


def union(name: str) -> dict[str, Any]:
    return {"kind": "union", "name": name}


def option(item: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "option", "item": item}


def choice(*items: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "choice", "items": list(items)}


def list_of(
    item: dict[str, Any], *, unique: bool = False, order: str | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": "list", "item": item}
    if unique:
        result["unique"] = True
    if order is not None:
        result["order"] = order
    return result


DIGEST = scalar("digest")
RECEIPT = scalar("receipt")
IDENT = scalar("id")
NAT = scalar("nat")
POS = scalar("pos")
BOOL = scalar("bool")
STRING = scalar("string")


def fields(*rows: tuple[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"name": name, "type": desc} for name, desc in rows]


def nullary(tag: str) -> dict[str, Any]:
    return {"tag": tag, "shape": "nullary"}


def args(tag: str, *descs: dict[str, Any]) -> dict[str, Any]:
    return {"tag": tag, "shape": "args", "args": list(descs)}


def field_variant(tag: str, *rows: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return {"tag": tag, "shape": "fields", "fields": fields(*rows)}


ENUMS: OrderedDict[str, dict[str, Any]] = OrderedDict([
    ("PublicReasonClassesV2", {"wireKind": "string", "values": PUBLIC_REASONS_V2}),
    ("ReleasePolicyLintClass", {"wireKind": "string", "values": LINT_CLASSES}),
    ("RawSolverResultV2", {"wireKind": "string", "values": ["SAT", "UNSAT", "UNKNOWN"]}),
    ("BlockerScopeV2", {"wireKind": "string", "values": BLOCKER_SCOPES_V2}),
])


RECORDS: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
UNIONS: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()


def add_record(name: str, *rows: tuple[str, dict[str, Any]]) -> None:
    RECORDS[name] = fields(*rows)


def add_union(name: str, *variants: dict[str, Any]) -> None:
    UNIONS[name] = list(variants)


add_union("QueryKindV2", *(nullary(value) for value in QUERY_KINDS))
add_union("CoalitionScopeV2", nullary("None"),
    field_variant("ConcreteCoalition", ("coalitionId", DIGEST)))
add_record("QueryDescriptorV2",
    ("queryKind", union("QueryKindV2")), ("entryScope", option(IDENT)),
    ("coalitionScope", union("CoalitionScopeV2")), ("releaseScope", option(IDENT)),
    ("componentScope", option(IDENT)), ("relationScope", option(IDENT)))
add_record("PublicQueryScheduleV2",
    ("formatId", literal("SPS-Public-Query-Schedule-v2")),
    ("artifactIdentityDigest", DIGEST), ("proofConfigurationDigest", DIGEST),
    ("queries", list_of(record("QueryDescriptorV2"), unique=True)))
add_record("OptionV2", ("name", STRING), ("value", choice(BOOL, NAT, STRING)))
add_record("ResourceLimitsV2",
    ("maxCallDepth", NAT), ("maxLoopCopies", NAT),
    ("maxExpandedInstructions", NAT), ("maxPaths", NAT), ("maxBytes", NAT),
    ("maxSolverMilliseconds", NAT), ("maxSolverMemoryBytes", NAT),
    ("maxEvidenceBytesPerBundle", POS), ("maxRestrictedDiagnosticBytes", NAT))
add_record("ProtectedEvidenceReferenceV2",
    ("receiptId", RECEIPT), ("sensitivity", literal("SecretBearing")),
    ("storageClass", literal("RestrictedVerifierStore")))
add_record("PublicDispositionReasonV2", ("reasonClassId", enum("PublicReasonClassesV2")))
add_union("P4OpenReasonV2", nullary("P4EvidenceProfileUnavailable"))
add_union("DeploymentStatusV2", args("Open", union("P4OpenReasonV2")))
# Current Rev4.1 identities and conformance bindings.  Every digest preimage is
# carried by one named, closed field below; there is deliberately no generic
# ``fieldId/canonicalBytes`` bag.
UNCHANGED_IDENTITY_INPUTS: OrderedDict[str, tuple[str, str, str]] = OrderedDict([
    ("llvmBuild", ("CanonicalLLVMBuildEvidenceV2", "SPS-Canonical-LLVM-Build-Evidence-v2", "llvmBuildDigest")),
    ("spsBuild", ("CanonicalSPSBuildEvidenceV2", "SPS-Canonical-SPS-Build-Evidence-v2", "spsBuildDigest")),
    ("passTrace", ("CanonicalPassTraceEvidenceV2", "SPS-Canonical-Pass-Trace-Evidence-v2", "completePassTraceDigest")),
    ("targetConfiguration", ("CanonicalTargetConfigurationV2", "SPS-Canonical-Target-Configuration-v2", "targetConfigurationDigest")),
    ("abi", ("CanonicalABISchemaV2", "SPS-Canonical-ABI-Schema-v2", "abiDigest")),
    ("policy", ("CanonicalPolicyManifestV2", "SPS-Canonical-Policy-Manifest-v2", "policyDigest")),
    ("releaseTable", ("CanonicalReleaseTableV2", "SPS-Canonical-Release-Table-v2", "releaseDigest")),
    ("contractTable", ("CanonicalContractTableV2", "SPS-Canonical-Contract-Table-v2", "contractDigest")),
    ("placementTable", ("CanonicalPlacementTableV2", "SPS-Canonical-Placement-Table-v2", "placementDigest")),
    ("aliasTopology", ("CanonicalAliasTopologyV2", "SPS-Canonical-Alias-Topology-v2", "aliasTopologyDigest")),
    ("allocaSizeBindings", ("CanonicalAllocaSizeBindingsV2", "SPS-Canonical-Alloca-Size-Bindings-v2", "allocaSizeBindingsDigest")),
    ("stableIRBindings", ("CanonicalStableIRBindingTableV2", "SPS-Canonical-Stable-IR-Binding-Table-v2", "stableIRBindingTableDigest")),
    ("transitionRuleTable", ("CanonicalTransitionRuleTableV2", "SPS-Canonical-Transition-Rule-Table-v2", "transitionRuleTableDigest")),
    ("observationSemantics", ("CanonicalObservationSemanticsV2", "SPS-Canonical-Observation-Semantics-v2", "observationSemanticsDigest")),
    ("latencyClassTable", ("CanonicalLatencyClassTableV2", "SPS-Canonical-Latency-Class-Table-v2", "latencyClassTableDigest")),
    ("timingEnvironment", ("CanonicalTimingEnvironmentV2", "SPS-Canonical-Timing-Environment-v2", "timingEnvironmentContractDigest")),
    ("stackProtectorPreflight", ("CanonicalStackProtectorPreflightV2", "SPS-Canonical-Stack-Protector-Preflight-v2", "stackProtectorPreflightDigest")),
    ("fpNaNPayloadSemantics", ("CanonicalFPNaNPayloadSemanticsV2", "SPS-Canonical-FP-NaN-Payload-Semantics-v2", "fpNaNPayloadSemanticsDigest")),
    ("policyReviewConfiguration", ("CanonicalPolicyReviewConfigurationV2", "SPS-Canonical-Policy-Review-Configuration-v2", "policyReviewConfigurationDigest")),
    ("entryScope", ("CanonicalEntryScopeTableV2", "SPS-Canonical-Entry-Scope-Table-v2", "entryScopeDigest")),
    ("profileConfiguration", ("CanonicalProfileConfigurationV2", "SPS-Canonical-Profile-Configuration-v2", "profileConfigurationDigest")),
    ("publicBounds", ("CanonicalPublicBoundsV2", "SPS-Canonical-Public-Bounds-v2", "publicBoundsDigest")),
    ("preconditions", ("CanonicalPreconditionsV2", "SPS-Canonical-Preconditions-v2", "preconditionsDigest")),
    ("policyExpressionSemantics", ("CanonicalPolicyExpressionSemanticsV2", "SPS-Canonical-Policy-Expression-Semantics-v2", "policyExpressionSemanticsDigest")),
    ("ponfSemantics", ("CanonicalPONFSemanticsV2", "SPS-Canonical-PONF-Semantics-v2", "ponfSemanticsDigest")),
    ("interfaceManifest", ("CanonicalInterfaceManifestV2", "SPS-Canonical-Interface-Manifest-v2", "interfaceManifestDigest")),
])

AUXILIARY_CONFORMANCE_INPUTS: OrderedDict[str, tuple[str, str]] = OrderedDict([
    ("globalRegionTable", ("CanonicalGlobalRegionTableV2", "SPS-Canonical-Global-Region-Table-v2")),
    ("preflightTaskSchedule", ("CanonicalPreflightTaskScheduleV2", "SPS-Canonical-Preflight-Task-Schedule-v2")),
])

for _field_name, (_record_name, _format_id, _identity_field) in UNCHANGED_IDENTITY_INPUTS.items():
    add_record(_record_name,
        ("formatId", literal(_format_id)),
        ("canonicalBytes", scalar("hex")),
        ("sha256", DIGEST))
for _field_name, (_record_name, _format_id) in AUXILIARY_CONFORMANCE_INPUTS.items():
    add_record(_record_name,
        ("formatId", literal(_format_id)),
        ("canonicalBytes", scalar("hex")),
        ("sha256", DIGEST))

add_record("CanonicalBitcodeV2",
    ("formatId", literal("SPS-Canonical-Bitcode-v2")),
    ("exactBytes", scalar("hex")), ("sha256", DIGEST))

add_record("ReleaseImplementationBindingV2",
    ("wrapperFunction", IDENT), ("emitMarkerInstructionId", IDENT))
add_record("ReleaseMarkerBindingRowV2",
    ("releaseId", IDENT), ("siteId", IDENT),
    ("implementation", record("ReleaseImplementationBindingV2")),
    ("flattenedIntegerWidths", list_of(POS)), ("releaseSpecV2Digest", DIGEST))
add_record("ReleaseMarkerBindingArtifactV2",
    ("formatId", literal("SPS-Release-Marker-Bindings-v2")),
    ("releaseTableFormatId", literal("SPS-ReleaseTable-v2")),
    ("intrinsicName", literal("llvm.sps.release")),
    ("rows", list_of(record("ReleaseMarkerBindingRowV2"), unique=True, order="canonical-element-bytes")))
add_record("ReleaseMarkerMachineMapRowV2",
    ("emitMarkerInstructionId", IDENT), ("mirPseudoId", IDENT),
    ("p4BoundaryId", IDENT))
add_record("ReleaseMarkerMachineMapV2",
    ("formatId", literal("SPS-Release-Marker-Machine-Map-v2")),
    ("rows", list_of(record("ReleaseMarkerMachineMapRowV2"), unique=True, order="canonical-element-bytes")))

add_record("LLVMReleaseIntrinsicDefinitionV2",
    ("formatId", literal("SPS-LLVM-Release-Intrinsic-Definition-v2")),
    ("intrinsicName", literal("llvm.sps.release")),
    ("resultType", literal("void")),
    ("operandEncoding", literal("DepthFirstLeftToRightReleaseTypeIntegerLeavesV2")),
    ("variadic", literal(True)),
    ("intrHasSideEffects", literal(True)),
    ("intrNoMem", literal(True)),
    ("intrNoDuplicate", literal(True)),
    ("intrNoMerge", literal(True)),
    ("speculatable", literal(False)))
add_record("AggregationSemanticsV2",
    ("formatId", literal("SPS-Model-Aggregation-Semantics-v2")),
    ("semanticsId", literal("SPS-Model-Aggregation-v2")),
    ("priority1", literal("RunFinalizationToReportingFailedV2")),
    ("priority2", literal("AcceptedBadReplayToCounterexample")),
    ("priority3", literal("OneExactUnknownTwoOrMoreOpenModelObligations")),
    ("priority4", literal("ProvedIffEmptyAndAllRequiredGatesClosed")),
    ("replayInvalidatingConflict", literal("RejectInconsistentInput")))
add_record("ReplayAcceptanceSemanticsV2",
    ("formatId", literal("SPS-Replay-Acceptance-Semantics-v2")),
    ("semanticsId", literal("SPS-Replay-Acceptance-v2")),
    ("profileId", literal("SPS-LLVM-NF-v2")),
    ("exactIdentityRequired", literal(True)),
    ("supportedConsumedPrefixRequired", literal(True)),
    ("independentReplayRequired", literal(True)),
    ("firstBadStateRequired", literal(True)),
    ("finalReceiptBindingRequired", literal(True)))

IDENTITY_INPUT_DIGEST_FIELDS = [spec[2] for spec in UNCHANGED_IDENTITY_INPUTS.values()
    if spec[2] != "interfaceManifestDigest"]
add_record("ArtifactIdentityV2",
    ("formatId", literal("SPS-ArtifactIdentity-v2")),
    ("profileId", literal("SPS-LLVM-NF-v2")),
    ("normalFormVersion", literal("SPS-LLVM-NF-v2")),
    ("finalWeakenerId", literal("SPSFinalWeaken_v2")),
    ("releaseTableFormatId", literal("SPS-ReleaseTable-v2")),
    ("releaseMarkerBindingsFormatId", literal("SPS-Release-Marker-Bindings-v2")),
    ("releaseMarkerMachineMapFormatId", literal("SPS-Release-Marker-Machine-Map-v2")),
    ("aggregationSemanticsId", literal("SPS-Model-Aggregation-v2")),
    ("replayAcceptanceSemanticsId", literal("SPS-Replay-Acceptance-v2")),
    ("canonicalBitcodeHash", DIGEST),
    *((name, DIGEST) for name in IDENTITY_INPUT_DIGEST_FIELDS),
    ("proofConfigurationDigest", DIGEST),
    ("queryScheduleDerivationDigest", DIGEST),
    ("releaseMarkerBindingsDigest", DIGEST),
    ("releaseMarkerMachineMapDigest", DIGEST),
    ("intrinsicDefinitionDigest", DIGEST),
    ("interfaceManifestDigest", DIGEST),
    ("aggregationSemanticsDigest", DIGEST),
    ("replayAcceptanceSemanticsDigest", DIGEST))

add_record("RequiredQueryScheduleV2",
    ("formatId", literal("SPS-Required-Query-Schedule-v2")),
    ("queries", list_of(record("QueryDescriptorV2"), unique=True)))
add_record("QueryScheduleDerivationV2",
    ("formatId", literal("SPS-Query-Schedule-Derivation-v2")),
    ("policyDigest", DIGEST), ("abiDigest", DIGEST),
    ("releaseDigest", DIGEST), ("contractDigest", DIGEST),
    ("entryScopeDigest", DIGEST), ("timingEnvironmentContractDigest", DIGEST),
    ("profileConfigurationDigest", DIGEST),
    ("requiredQuerySchedule", record("RequiredQueryScheduleV2")))
add_record("ProofConfigurationV2",
    ("formatId", literal("SPS-Proof-Configuration-v2")),
    ("profileId", literal("SPS-LLVM-NF-v2")),
    ("artifactIdentityFormatId", literal("SPS-ArtifactIdentity-v2")),
    ("aggregationSemantics", literal("SPS-Model-Aggregation-v2")),
    ("aggregationSemanticsDigest", DIGEST),
    ("replayAcceptanceSemantics", literal("SPS-Replay-Acceptance-v2")),
    ("replayAcceptanceSemanticsDigest", DIGEST),
    ("queryKinds", list_of(union("QueryKindV2"), unique=True, order="QueryKindV2")),
    ("requiredQuerySchedule", record("RequiredQueryScheduleV2")),
    ("publicReasonClasses", list_of(enum("PublicReasonClassesV2"), unique=True, order="PublicReasonClassesV2")),
    ("resourceLimits", record("ResourceLimitsV2")),
    ("restrictedEvidenceStoreContractDigest", DIGEST),
    ("exactVerifierBuildDigest", DIGEST))

add_record("ArtifactIdentityEvidenceV2",
    ("formatId", literal("SPS-Artifact-Identity-Evidence-v2")),
    ("profileId", literal("SPS-LLVM-NF-v2")),
    ("artifactIdentityDigest", DIGEST),
    ("artifactIdentity", record("ArtifactIdentityV2")),
    ("canonicalBitcode", record("CanonicalBitcodeV2")),
    *((field_name, record(spec[0])) for field_name, spec in UNCHANGED_IDENTITY_INPUTS.items()),
    *((field_name, record(spec[0])) for field_name, spec in AUXILIARY_CONFORMANCE_INPUTS.items()),
    ("proofConfiguration", record("ProofConfigurationV2")),
    ("queryScheduleDerivation", record("QueryScheduleDerivationV2")),
    ("releaseMarkerBindings", record("ReleaseMarkerBindingArtifactV2")),
    ("releaseMarkerMachineMap", record("ReleaseMarkerMachineMapV2")),
    ("intrinsicDefinition", record("LLVMReleaseIntrinsicDefinitionV2")),
    ("aggregationSemantics", record("AggregationSemanticsV2")),
    ("replayAcceptanceSemantics", record("ReplayAcceptanceSemanticsV2")))

add_record("SPSLLVMNFManifestV2",
    ("formatId", literal("SPS-LLVM-NF-Manifest-v2")),
    ("profileId", literal("SPS-LLVM-NF-v2")),
    ("llvmBaseline", literal("llvmorg-22.1.8")),
    ("llvmUpstreamCommit", literal("ca7933e47d3a3451d81e72ac174dcb5aa28b59d1")),
    ("intrinsicName", literal("llvm.sps.release")),
    ("finalWeakenerId", literal("SPSFinalWeaken_v2")),
    ("releaseTableFormatId", literal("SPS-ReleaseTable-v2")),
    ("releaseMarkerBindingsDigest", DIGEST),
    ("releaseMarkerMachineMapDigest", DIGEST),
    ("intrinsicDefinitionDigest", DIGEST),
    ("aggregationSemanticsDigest", DIGEST),
    ("replayAcceptanceSemanticsDigest", DIGEST),
    ("artifactIdentity", record("ArtifactIdentityV2")),
    ("artifactIdentityEvidence", record("ArtifactIdentityEvidenceV2")))


# Restricted replay and aggregation interfaces.
add_record("AcceptedBadReplayV2",
    ("formatId", literal("SPS-Accepted-Bad-Replay-v2")),
    ("artifactIdentityDigest", DIGEST), ("proofConfigurationDigest", DIGEST),
    ("queryScheduleDigest", DIGEST), ("queryOrdinal", NAT),
    ("query", record("QueryDescriptorV2")),
    ("replaySemantics", literal("SPS-Replay-Acceptance-v2")),
    ("firstBadStep", NAT), ("firstBadStateDigest", DIGEST),
    ("finalReceiptId", RECEIPT),
    ("protectedEvidence", record("ProtectedEvidenceReferenceV2")))
add_union("BlockerReasonV2",
    field_variant("ModelBlocker", ("reason", record("PublicDispositionReasonV2"))),
    field_variant("ReportingBlocker", ("reason", union("SPSReportingFailureReasonV2"))))
add_record("BlockerRecordV2",
    ("formatId", literal("SPS-Blocker-Record-v2")),
    ("scope", enum("BlockerScopeV2")), ("phaseOrdinal", NAT),
    ("scheduleOrdinal", option(NAT)),
    ("reason", union("BlockerReasonV2")),
    ("restrictedDetailDigest", DIGEST))
add_record("AggregationInputV2",
    ("formatId", literal("SPS-Aggregation-Input-v2")),
    ("artifactIdentityDigest", DIGEST),
    ("proofConfigurationDigest", DIGEST),
    ("queryScheduleDigest", DIGEST),
    ("acceptedBadReplay", option(record("AcceptedBadReplayV2"))),
    ("blockers", list_of(record("BlockerRecordV2"), unique=True, order="canonical-element-bytes")),
    ("allRequiredGatesClosed", BOOL))


# Current Rev4.1 public report. Every reason-bearing carrier is closed, so an
# obsolete mismatch reason cannot schema-parse in a current report.
add_union("QueryDispositionV2", nullary("CandidateOnly"),
    nullary("ValidatedExistentialWitness"), nullary("ConstrainedOrUnexercised"),
    nullary("Discharged"), args("Unknown", record("PublicDispositionReasonV2")))
add_record("SolverIdentityV2",
    ("solverName", STRING), ("solverVersion", STRING),
    ("solverBuildDigest", DIGEST), ("exactSolverOptions", list_of(record("OptionV2"))),
    ("resourceLimits", record("ResourceLimitsV2")))
add_record("PONFResultArtifactV2",
    ("formatId", literal("SPS-PONF-Result-v2")), ("canonicalPONFDigest", DIGEST),
    ("exactFormulaDigest", DIGEST), ("proofConfigurationDigest", DIGEST),
    ("solver", record("SolverIdentityV2")), ("rawSolverResult", enum("RawSolverResultV2")),
    ("protectedEvidence", record("ProtectedEvidenceReferenceV2")),
    ("queryDisposition", union("QueryDispositionV2")))
add_union("PublicQueryOutcomeV2",
    field_variant("NotConstructedV2", ("reason", record("PublicDispositionReasonV2")),
        ("protectedEvidence", record("ProtectedEvidenceReferenceV2"))),
    args("Constructed", record("PONFResultArtifactV2")))
add_record("PublicQueryResultRowV2", ("queryOrdinal", NAT),
    ("outcome", union("PublicQueryOutcomeV2")))
add_union("ReleaseReviewDispositionV2", nullary("ValidatedDormantZero"),
    nullary("ValidatedNotApplicableZero"), nullary("ExactAdmittedMaximum"),
    args("ConservativeDeclaredCap", record("PublicDispositionReasonV2")))
add_record("ReleasePolicyReviewSummandV2",
    ("entryId", IDENT), ("coalitionId", DIGEST), ("releaseId", IDENT),
    ("audienceApplies", BOOL), ("disposition", union("ReleaseReviewDispositionV2")),
    ("reviewMultiplicity", NAT), ("declaredRangeCardinality", POS),
    ("contributionBits", NAT))
add_record("ReleasePolicyReviewTotalV2",
    ("entryId", IDENT), ("coalitionId", DIGEST), ("totalBits", NAT))
add_record("ReleasePolicyLintV2",
    ("lintClass", enum("ReleasePolicyLintClass")),
    ("entryScope", option(IDENT)), ("coalitionScope", union("CoalitionScopeV2")),
    ("releaseScope", option(IDENT)), ("componentScope", option(IDENT)))
add_union("PolicyReviewStatusV2", nullary("Complete"), nullary("Findings"),
    args("Incomplete", record("PublicDispositionReasonV2")))
add_record("ReleasePolicyReviewReportV2",
    ("formatId", literal("SPS-Release-Policy-Review-v2")),
    ("artifactIdentityDigest", DIGEST), ("policyDigest", DIGEST),
    ("releaseDigest", DIGEST), ("policyReviewConfigurationDigest", DIGEST),
    ("summands", list_of(record("ReleasePolicyReviewSummandV2"))),
    ("totals", list_of(record("ReleasePolicyReviewTotalV2"))),
    ("lints", list_of(record("ReleasePolicyLintV2"), unique=True)),
    ("status", union("PolicyReviewStatusV2")))
add_record("PreflightTriageSummaryV2",
    ("artifactIdentityDigest", DIGEST), ("taskId", IDENT),
    ("disposition", literal("NonAuthoritativePreflightOnly")),
    ("protectedEvidence", record("ProtectedEvidenceReferenceV2")))
add_union("ModelStatusV2", nullary("Proved"), args("Counterexample", RECEIPT),
    args("Unknown", record("PublicDispositionReasonV2")))
add_record("SPSPublicReportV2",
    ("formatId", literal("SPS-Public-Report-v2")),
    ("profileId", literal("SPS-LLVM-NF-v2")),
    ("artifactIdentityFormatId", literal("SPS-ArtifactIdentity-v2")),
    ("artifactIdentityDigest", DIGEST), ("proofConfigurationDigest", DIGEST),
    ("querySchedule", record("PublicQueryScheduleV2")), ("queryScheduleDigest", DIGEST),
    ("queryResults", list_of(record("PublicQueryResultRowV2"))),
    ("preflightTaskScheduleDigest", DIGEST),
    ("preflightSummaries", list_of(record("PreflightTriageSummaryV2"))),
    ("modelStatus", union("ModelStatusV2")),
    ("deploymentStatus", union("DeploymentStatusV2")),
    ("policyReviewStatus", union("PolicyReviewStatusV2")),
    ("releasePolicyReview", record("ReleasePolicyReviewReportV2")),
    ("runEvidence", record("ProtectedEvidenceReferenceV2")),
    ("statusNoninterference", literal("PolicyReviewDoesNotAffectModelOrDeploymentV2")))
add_union("ConfigurationRejectionReasonV2", *(nullary(value) for value in CONFIG_REASONS_V2))
add_union("SPSReportingFailureReasonV2", *(nullary(value) for value in REPORT_FAILURES_V2))
add_record("SPSConfigurationRejectionReportV2",
    ("formatId", literal("SPS-Configuration-Rejection-v2")),
    ("disposition", literal("NoModelStatus")),
    ("reason", union("ConfigurationRejectionReasonV2")))
add_record("SPSReportingFailureReportV2",
    ("formatId", literal("SPS-Reporting-Failure-v2")),
    ("disposition", literal("NoModelStatus")),
    ("reason", union("SPSReportingFailureReasonV2")))
add_union("SPSRunReportV2",
    field_variant("ConfigurationRejectedV2", ("report", record("SPSConfigurationRejectionReportV2"))),
    field_variant("ReportingFailedV2", ("report", record("SPSReportingFailureReportV2"))),
    field_variant("CompletedV2", ("report", record("SPSPublicReportV2"))))

# The decision binding is the semantic validation root that contains both the
# restricted aggregation inputs and the public output.  Without this closed
# object, XF-REPLAY-002 cannot be checked because its two receipts live in
# different artifacts.
add_record("AggregationDecisionV2",
    ("formatId", literal("SPS-Aggregation-Decision-v2")),
    ("identityEvidence", record("ArtifactIdentityEvidenceV2")),
    ("input", record("AggregationInputV2")),
    ("runReport", union("SPSRunReportV2")))


ROOT_SCHEMA_IDS: OrderedDict[str, str] = OrderedDict([
    ("common.schema.json", BASE_ID + "schemas/common.schema.json"),
    ("conformance.schema.json", BASE_ID + "schemas/conformance.schema.json"),
    ("reports.schema.json", BASE_ID + "schemas/reports.schema.json"),
    ("restricted.schema.json", BASE_ID + "schemas/restricted.schema.json"),
    ("package.schema.json", BASE_ID + "schemas/package.schema.json"),
])
add_record("InterfaceManifestBundleV2",
    ("path", literal("sps-rev4.1.bundle.json")), ("sha256", DIGEST))
add_record("InterfaceManifestRootSchemaIdsV2",
    *((filename, literal(schema_id)) for filename, schema_id in ROOT_SCHEMA_IDS.items()))
add_record("InterfaceManifestFileV2", ("path", STRING), ("sha256", DIGEST))
add_record("SPSInterfaceManifestV2",
    ("formatId", literal("SPS-Interface-Manifest-v2")),
    ("schemaSetId", literal(SCHEMA_SET_ID)),
    ("specRevision", literal("4.1")),
    ("sourceRevision", literal(SOURCE_REVISION)),
    ("bundle", record("InterfaceManifestBundleV2")),
    ("rootSchemaIds", record("InterfaceManifestRootSchemaIdsV2")),
    ("files", list_of(record("InterfaceManifestFileV2"), unique=True, order="manifest-path")))


CURRENT_ROOTS = [
    "SPSRunReportV2", "SPSPublicReportV2", "ArtifactIdentityV2",
    "ArtifactIdentityEvidenceV2", "SPSLLVMNFManifestV2",
    "ProofConfigurationV2", "QueryScheduleDerivationV2",
    "ReleaseMarkerBindingArtifactV2",
    "ReleaseMarkerMachineMapV2", "AcceptedBadReplayV2",
    "BlockerRecordV2", "AggregationInputV2", "AggregationDecisionV2",
    "SPSConformanceInterfaceManifestV2",
]


ROOTS: OrderedDict[str, tuple[str, list[str]]] = OrderedDict([
    ("common.schema.json", (ROOT_SCHEMA_IDS["common.schema.json"], ["ModelStatusV2", "DeploymentStatusV2", "PolicyReviewStatusV2"])),
    ("conformance.schema.json", (ROOT_SCHEMA_IDS["conformance.schema.json"], [
        "ArtifactIdentityV2", "ArtifactIdentityEvidenceV2", "ReleaseImplementationBindingV2",
        "ReleaseMarkerBindingArtifactV2", "ReleaseMarkerMachineMapV2",
        "LLVMReleaseIntrinsicDefinitionV2", "AggregationSemanticsV2",
        "ReplayAcceptanceSemanticsV2", "SPSLLVMNFManifestV2", "ProofConfigurationV2",
        "QueryScheduleDerivationV2", "SPSConformanceInterfaceManifestV2",
    ])),
    ("reports.schema.json", (ROOT_SCHEMA_IDS["reports.schema.json"], ["SPSRunReportV2", "SPSPublicReportV2"])),
    ("restricted.schema.json", (ROOT_SCHEMA_IDS["restricted.schema.json"], ["AcceptedBadReplayV2", "BlockerRecordV2", "AggregationInputV2", "AggregationDecisionV2"])),
    ("package.schema.json", (ROOT_SCHEMA_IDS["package.schema.json"], ["SPSInterfaceManifestV2"])),
])


SEMANTIC_RULES = OrderedDict([
    ("XF-REPORT-001", "Only CompletedV2 contains ModelStatus or run evidence."),
    ("XF-REPORT-002", "Public evidence is receipt-only, receipts occupy their fixed roles, and no receipt is reused."),
    ("XF-REPORT-003", "A completed report is identity/configuration/digest consistent and covers its complete ordered query schedule and required policy review."),
    ("XF-REPLAY-001", "AcceptedBadReplayV2 cannot coexist with a ReplayInvalidating blocker."),
    ("XF-REPLAY-002", "The accepted replay binds its exact query and receipt, and that receipt equals the public counterexample receipt."),
    ("XF-AGG-001", "Aggregation follows RunFinalization, accepted replay, blocker-count, then complete-proof priority; empty blockers yield Proved only when every required gate is closed."),
    ("XF-AGG-002", "RunFinalization uses a reporting reason; other blocker scopes use a model reason."),
    ("XF-INTRINSIC-001", "Intrinsic payload widths are nonempty and release, site, wrapper, instruction, MIR pseudo, and P4 boundary bindings resolve one-to-one."),
    ("XF-IDENTITY-001", "Every named V2 identity preimage is canonical, hashes exactly, and binds NFv2, FinalWeaken_v2, ReleaseTable-v2, intrinsic properties, marker maps, interface manifest, Aggregation-v2, and Replay-Acceptance-v2."),
    ("XF-PAYLOAD-001", "Every canonical conformance-input envelope contains the exact field inventory and closed literals of its named normative payload; arbitrary canonical JSON is rejected."),
])

add_record("SPSConformanceInterfaceManifestV2",
    ("formatId", literal("SPS-Conformance-Interface-Manifest-v2")),
    ("schemaSetId", literal(SCHEMA_SET_ID)),
    ("specRevision", literal("4.1")),
    ("sourceRevision", literal(SOURCE_REVISION)),
    ("rootSchemaIds", record("InterfaceManifestRootSchemaIdsV2")),
    ("currentRoots", list_of(STRING, unique=True)),
    ("requiredIdentityFields", list_of(STRING, unique=True)),
    ("requiredEvidenceFields", list_of(STRING, unique=True)),
    ("publicReasonClasses", list_of(enum("PublicReasonClassesV2"), unique=True, order="PublicReasonClassesV2")),
    ("semanticRuleIds", list_of(STRING, unique=True)))


def schema_for(desc: dict[str, Any]) -> dict[str, Any]:
    kind = desc["kind"]
    if kind == "digest" or kind == "receipt":
        return {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    if kind == "hex":
        return {"type": "string", "pattern": "^(?:[0-9a-f]{2})*$"}
    if kind == "id":
        return {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9._:-]{0,127}$"}
    if kind == "nat":
        return {"type": "integer", "minimum": 0}
    if kind == "pos":
        return {"type": "integer", "minimum": 1}
    if kind == "bool":
        return {"type": "boolean"}
    if kind == "string":
        return {"type": "string"}
    if kind == "literal":
        return {"const": desc["value"]}
    if kind in {"enum", "record", "union"}:
        return {"$ref": BUNDLE_ID + "#/$defs/" + desc["name"]}
    if kind == "list":
        result = {"type": "array", "items": schema_for(desc["item"])}
        if desc.get("unique"):
            result["uniqueItems"] = True
            result["x-sps-collection"] = "canonical-unique-list"
            result["x-sps-order"] = desc.get("order", "semantic-order")
        return result
    if kind == "option":
        return {"oneOf": [
            {"type": "object", "properties": {"tag": {"const": "None"}},
             "required": ["tag"], "additionalProperties": False,
             "x-sps-canonical-field-order": ["tag"]},
            {"type": "object", "properties": {"tag": {"const": "Some"}, "value": schema_for(desc["item"])},
             "required": ["tag", "value"], "additionalProperties": False,
             "x-sps-canonical-field-order": ["tag", "value"]},
        ]}
    if kind == "choice":
        return {"oneOf": [schema_for(item) for item in desc["items"]]}
    raise AssertionError(f"unknown descriptor kind: {kind}")


def record_schema(rows: list[dict[str, Any]]) -> dict[str, Any]:
    names = [row["name"] for row in rows]
    return {
        "type": "object",
        "properties": OrderedDict((row["name"], schema_for(row["type"])) for row in rows),
        "required": names,
        "additionalProperties": False,
        "x-sps-canonical-field-order": names,
    }


def union_schema(variants: list[dict[str, Any]]) -> dict[str, Any]:
    choices = []
    for variant in variants:
        properties: OrderedDict[str, Any] = OrderedDict([("tag", {"const": variant["tag"]})])
        required = ["tag"]
        if variant["shape"] == "args":
            properties["args"] = {
                "type": "array", "prefixItems": [schema_for(item) for item in variant["args"]],
                "minItems": len(variant["args"]), "maxItems": len(variant["args"]),
            }
            required.append("args")
        elif variant["shape"] == "fields":
            for row in variant["fields"]:
                properties[row["name"]] = schema_for(row["type"])
                required.append(row["name"])
        choices.append({
            "type": "object", "properties": properties, "required": required,
            "additionalProperties": False, "x-sps-canonical-field-order": required,
        })
    return {"oneOf": choices}


def all_defs() -> OrderedDict[str, Any]:
    result: OrderedDict[str, Any] = OrderedDict()
    for name, spec in ENUMS.items():
        if spec["wireKind"] == "string":
            result[name] = {"type": "string", "enum": spec["values"]}
    for name, rows in RECORDS.items():
        result[name] = record_schema(rows)
    for name, variants in UNIONS.items():
        result[name] = union_schema(variants)
    return result


def wrapper_schema(schema_id: str, roots: list[str]) -> OrderedDict[str, Any]:
    refs = [{"$ref": BUNDLE_ID + "#/$defs/" + root} for root in roots]
    return OrderedDict([
        ("$schema", SCHEMA_DRAFT), ("$id", schema_id),
        ("title", "SPS Rev4.1 interface roots: " + ", ".join(roots)),
        (("$ref" if len(refs) == 1 else "oneOf"), (refs[0]["$ref"] if len(refs) == 1 else refs)),
    ])


def registry() -> OrderedDict[str, Any]:
    formats: OrderedDict[str, str] = OrderedDict()
    for name, rows in RECORDS.items():
        for row in rows:
            if row["name"] == "formatId" and row["type"]["kind"] == "literal":
                formats[name] = row["type"]["value"]
    return OrderedDict([
        ("formatId", "SPS-Interface-Registry-v2"),
        ("schemaSetId", SCHEMA_SET_ID),
        ("specRevision", "4.1"),
        ("currentProfileId", "SPS-LLVM-NF-v2"),
        ("interfacePolicy", OrderedDict([
            ("currentRoots", CURRENT_ROOTS),
            ("versionPolicy", "v2-only"),
        ])),
        ("rootSchemaIds", OrderedDict((name, schema_id) for name, (schema_id, _) in ROOTS.items())),
        ("formatLiterals", formats),
        ("enums", OrderedDict((name, spec) for name, spec in ENUMS.items())),
        ("records", OrderedDict((name, OrderedDict([
            ("fields", rows), ("canonicalFieldOrder", [row["name"] for row in rows])
        ])) for name, rows in RECORDS.items())),
        ("unions", OrderedDict((name, OrderedDict([
            ("variants", variants), ("canonicalVariantOrder", [v["tag"] for v in variants])
        ])) for name, variants in UNIONS.items())),
        ("semanticRules", [OrderedDict([("ruleId", key), ("meaning", value)]) for key, value in SEMANTIC_RULES.items()]),
    ])


ZERO = "0" * 64
ONE = "1" * 64
TWO = "2" * 64
THREE = "3" * 64


def protected(receipt: str = ONE) -> OrderedDict[str, Any]:
    return OrderedDict([
        ("receiptId", receipt), ("sensitivity", "SecretBearing"),
        ("storageClass", "RestrictedVerifierStore"),
    ])


def blocker(scope: str) -> OrderedDict[str, Any]:
    if scope == "RunFinalization":
        reason: OrderedDict[str, Any] = OrderedDict([
            ("tag", "ReportingBlocker"),
            ("reason", OrderedDict([("tag", "EvidenceFinalizationFailure")])),
        ])
    else:
        reason = OrderedDict([
            ("tag", "ModelBlocker"),
            ("reason", OrderedDict([("reasonClassId", "SolverTimeout" if scope == "ProofCompletion" else "PONFFPArithmeticUnsupported")])),
        ])
    return OrderedDict([
        ("formatId", "SPS-Blocker-Record-v2"), ("scope", scope),
        ("phaseOrdinal", 2), ("scheduleOrdinal", OrderedDict([("tag", "None")])),
        ("reason", reason),
        ("restrictedDetailDigest", ZERO),
    ])


def option_id(value: str | None) -> OrderedDict[str, Any]:
    if value is None:
        return OrderedDict([("tag", "None")])
    return OrderedDict([("tag", "Some"), ("value", value)])


SCHEDULE_KIND_ORDER = [
    "AuditAll", "ReleaseActivation", "ReleaseConformance", "AdmissionNonempty",
    "LLVMDefinedness", "Initialization", "BoundAdequacy", "StructuralAlloca",
    "OutputClosure", "HighVariation", "CouplingTotality", "CouplingFiberTotal",
    "CouplingSymmetry", "CouplingSchedulePreservation",
]


def query_descriptor(
    kind: str = "AuditAll", *, entry_id: str = "entry.main",
    coalition_id: str | None = None, release_id: str | None = None,
    component_id: str | None = None, relation_id: str | None = None,
) -> OrderedDict[str, Any]:
    coalition_kinds = {
        "AuditAll", "HighVariation", "CouplingTotality", "CouplingFiberTotal",
        "CouplingSymmetry", "CouplingSchedulePreservation",
    }
    release_kinds = {"ReleaseConformance", "ReleaseActivation"}
    component_kinds = {"HighVariation"}
    relation_kinds = {
        "CouplingTotality", "CouplingFiberTotal", "CouplingSymmetry",
        "CouplingSchedulePreservation",
    }
    if coalition_id is None and kind in coalition_kinds:
        coalition_id = sha256(canonical_bytes(["principal.fixture"]))
    if release_id is None and kind in release_kinds:
        release_id = "release.one"
    if component_id is None and kind in component_kinds:
        component_id = "component.high"
    if relation_id is None and kind in relation_kinds:
        relation_id = "relation.one"
    return OrderedDict([
        ("queryKind", OrderedDict([("tag", kind)])),
        ("entryScope", option_id(entry_id)),
        ("coalitionScope", OrderedDict([
            ("tag", "ConcreteCoalition"), ("coalitionId", coalition_id),
        ]) if kind in coalition_kinds else OrderedDict([("tag", "None")])),
        ("releaseScope", option_id(release_id if kind in release_kinds else None)),
        ("componentScope", option_id(component_id if kind in component_kinds else None)),
        ("relationScope", option_id(relation_id if kind in relation_kinds else None)),
    ])


def canonical_map(rows: Any) -> OrderedDict[Any, Any]:
    return OrderedDict((row["key"], row["value"]) for row in rows)


def derived_adversary_coalitions(
    maximal_coalitions: list[list[str]],
) -> list[tuple[str, list[str]]]:
    """Return the canonical downward closure of the authored maxima."""
    coalition_sets: set[tuple[str, ...]] = set()
    for maximal in maximal_coalitions:
        principals = sorted(set(maximal))
        for mask in range(1 << len(principals)):
            coalition_sets.add(tuple(
                principal for index, principal in enumerate(principals)
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


def required_query_schedule(
    canonical_inputs: OrderedDict[str, Any] | None = None,
) -> OrderedDict[str, Any]:
    if canonical_inputs is None:
        names = [
            "policy", "abi", "releaseTable", "contractTable", "entryScope",
            "timingEnvironment",
        ]
        canonical_inputs = OrderedDict((name, canonical_input(name)) for name in names)
    decoded = {
        name: require_canonical(bytes.fromhex(canonical_inputs[name]["canonicalBytes"]))
        for name in [
            "policy", "abi", "releaseTable", "contractTable", "entryScope",
            "timingEnvironment",
        ]
    }
    policy = decoded["policy"]
    entries = [row["key"] for row in policy["entries"]]
    coalitions = derived_adversary_coalitions(
        policy["maximalAdversaryCoalitions"])
    components = canonical_map(policy["components"])
    member_visibility = canonical_map(policy["componentVisibility"]["memberVisible"])
    world_visible = set(policy["componentVisibility"]["worldVisible"])
    joint_visibility = policy["componentVisibility"]["minimallyJointVisible"]
    release_entries = {entry["releaseId"]: entry for entry in decoded["releaseTable"]["entries"]}
    entry_scopes = {row["entryId"]: row for row in decoded["entryScope"]["rows"]}
    queries: list[OrderedDict[str, Any]] = []
    for entry_id in entries:
        for coalition_id, _principals in coalitions:
            queries.append(query_descriptor(
                "AuditAll", entry_id=entry_id, coalition_id=coalition_id))
    for entry_id in entries:
        for release_id, release in release_entries.items():
            claims = canonical_map(release["activationClaims"])
            if entry_id in claims:
                queries.append(query_descriptor(
                    "ReleaseActivation", entry_id=entry_id, release_id=release_id))
                if claims[entry_id]["tag"] != "NotApplicable":
                    queries.append(query_descriptor(
                        "ReleaseConformance", entry_id=entry_id, release_id=release_id))
    for kind in [
        "AdmissionNonempty", "LLVMDefinedness", "Initialization",
        "BoundAdequacy", "StructuralAlloca", "OutputClosure",
    ]:
        queries.extend(query_descriptor(kind, entry_id=entry_id) for entry_id in entries)
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
                    for joint_principals, visible_component in joint_visibility
                )
                if not visible:
                    queries.append(query_descriptor(
                        "HighVariation", entry_id=entry_id,
                        coalition_id=coalition_id, component_id=component_id))

    for contract in decoded["contractTable"]["contracts"]:
        relation_rows: list[tuple[str, str]] = []
        boundaries = set(canonical_map(contract["occurrences"]))
        for row in contract["pairedChoiceCoupling"]:
            relation = row["value"]
            relation_rows.append((row["key"], relation["relationId"]))
        for entry_id, scope in entry_scopes.items():
            if boundaries.intersection(scope["reachableBoundaryIds"]):
                for coalition_id, relation_id in relation_rows:
                    for kind in [
                        "CouplingTotality", "CouplingFiberTotal", "CouplingSymmetry",
                        "CouplingSchedulePreservation",
                    ]:
                        queries.append(query_descriptor(
                            kind, entry_id=entry_id, coalition_id=coalition_id,
                            relation_id=relation_id))
    for row in decoded["timingEnvironment"]["pairedChoiceCoupling"]:
        relation = row["value"]
        for entry_id in entries:
            for kind in [
                "CouplingTotality", "CouplingFiberTotal", "CouplingSymmetry",
                "CouplingSchedulePreservation",
            ]:
                queries.append(query_descriptor(
                    kind, entry_id=entry_id, coalition_id=row["key"],
                    relation_id=relation["relationId"]))
    unique_queries = {canonical_bytes(query): query for query in queries}
    queries = sorted(
        unique_queries.values(),
        key=lambda query: (
            SCHEDULE_KIND_ORDER.index(query["queryKind"]["tag"]),
            canonical_bytes(query),
        ),
    )
    return OrderedDict([
        ("formatId", "SPS-Required-Query-Schedule-v2"),
        ("queries", queries),
    ])


def resource_limits() -> OrderedDict[str, Any]:
    return OrderedDict([
        ("maxCallDepth", 8), ("maxLoopCopies", 16),
        ("maxExpandedInstructions", 4096), ("maxPaths", 4096),
        ("maxBytes", 1048576), ("maxSolverMilliseconds", 30000),
        ("maxSolverMemoryBytes", 1073741824),
        ("maxEvidenceBytesPerBundle", 65536),
        ("maxRestrictedDiagnosticBytes", 16384),
    ])


def aggregation_semantics() -> OrderedDict[str, Any]:
    return OrderedDict([
        ("formatId", "SPS-Model-Aggregation-Semantics-v2"),
        ("semanticsId", "SPS-Model-Aggregation-v2"),
        ("priority1", "RunFinalizationToReportingFailedV2"),
        ("priority2", "AcceptedBadReplayToCounterexample"),
        ("priority3", "OneExactUnknownTwoOrMoreOpenModelObligations"),
        ("priority4", "ProvedIffEmptyAndAllRequiredGatesClosed"),
        ("replayInvalidatingConflict", "RejectInconsistentInput"),
    ])


def replay_acceptance_semantics() -> OrderedDict[str, Any]:
    return OrderedDict([
        ("formatId", "SPS-Replay-Acceptance-Semantics-v2"),
        ("semanticsId", "SPS-Replay-Acceptance-v2"),
        ("profileId", "SPS-LLVM-NF-v2"),
        ("exactIdentityRequired", True),
        ("supportedConsumedPrefixRequired", True),
        ("independentReplayRequired", True),
        ("firstBadStateRequired", True),
        ("finalReceiptBindingRequired", True),
    ])


def intrinsic_definition() -> OrderedDict[str, Any]:
    return OrderedDict([
        ("formatId", "SPS-LLVM-Release-Intrinsic-Definition-v2"),
        ("intrinsicName", "llvm.sps.release"),
        ("resultType", "void"),
        ("operandEncoding", "DepthFirstLeftToRightReleaseTypeIntegerLeavesV2"),
        ("variadic", True),
        ("intrHasSideEffects", True),
        ("intrNoMem", True),
        ("intrNoDuplicate", True),
        ("intrNoMerge", True),
        ("speculatable", False),
    ])


def proof_configuration(
    *, duplicate_reason: bool = False,
    canonical_inputs: OrderedDict[str, Any] | None = None,
) -> OrderedDict[str, Any]:
    reasons = list(PUBLIC_REASONS_V2)
    if duplicate_reason:
        reasons.insert(1, reasons[0])
    aggregation_digest = sha256(canonical_bytes(aggregation_semantics()))
    replay_digest = sha256(canonical_bytes(replay_acceptance_semantics()))
    return OrderedDict([
        ("formatId", "SPS-Proof-Configuration-v2"),
        ("profileId", "SPS-LLVM-NF-v2"),
        ("artifactIdentityFormatId", "SPS-ArtifactIdentity-v2"),
        ("aggregationSemantics", "SPS-Model-Aggregation-v2"),
        ("aggregationSemanticsDigest", aggregation_digest),
        ("replayAcceptanceSemantics", "SPS-Replay-Acceptance-v2"),
        ("replayAcceptanceSemanticsDigest", replay_digest),
        ("queryKinds", [OrderedDict([("tag", item)]) for item in QUERY_KINDS]),
        ("requiredQuerySchedule", required_query_schedule(canonical_inputs)),
        ("publicReasonClasses", reasons),
        ("resourceLimits", resource_limits()),
        ("restrictedEvidenceStoreContractDigest", ZERO),
        ("exactVerifierBuildDigest", ONE),
    ])


def query_schedule_derivation(
    canonical_inputs: OrderedDict[str, Any], proof: OrderedDict[str, Any],
) -> OrderedDict[str, Any]:
    return OrderedDict([
        ("formatId", "SPS-Query-Schedule-Derivation-v2"),
        ("policyDigest", canonical_inputs["policy"]["sha256"]),
        ("abiDigest", canonical_inputs["abi"]["sha256"]),
        ("releaseDigest", canonical_inputs["releaseTable"]["sha256"]),
        ("contractDigest", canonical_inputs["contractTable"]["sha256"]),
        ("entryScopeDigest", canonical_inputs["entryScope"]["sha256"]),
        ("timingEnvironmentContractDigest", canonical_inputs["timingEnvironment"]["sha256"]),
        ("profileConfigurationDigest", canonical_inputs["profileConfiguration"]["sha256"]),
        ("requiredQuerySchedule", proof["requiredQuerySchedule"]),
    ])


def conformance_interface_manifest() -> OrderedDict[str, Any]:
    return OrderedDict([
        ("formatId", "SPS-Conformance-Interface-Manifest-v2"),
        ("schemaSetId", SCHEMA_SET_ID),
        ("specRevision", "4.1"),
        ("sourceRevision", SOURCE_REVISION),
        ("rootSchemaIds", OrderedDict(ROOT_SCHEMA_IDS)),
        ("currentRoots", CURRENT_ROOTS),
        ("requiredIdentityFields", [row["name"] for row in RECORDS["ArtifactIdentityV2"]]),
        ("requiredEvidenceFields", [row["name"] for row in RECORDS["ArtifactIdentityEvidenceV2"]]),
        ("publicReasonClasses", PUBLIC_REASONS_V2),
        ("semanticRuleIds", list(SEMANTIC_RULES)),
    ])


def policy_semantics_version() -> OrderedDict[str, Any]:
    return OrderedDict([
        ("languageId", "SPS-PolicyExpr-NF-v2"),
        ("grammarAndTypingVersion", "v2"),
        ("denotationVersion", "v2"),
        ("primitiveTableVersion", "v2"),
    ])


def release_spec() -> OrderedDict[str, Any]:
    return OrderedDict([
        ("releaseId", "release.one"),
        ("site", "site.release.one"),
        ("implementation", OrderedDict([
            ("wrapperFunction", "wrapper.release.one"),
            ("emitMarkerInstructionId", "inst.release.one"),
        ])),
        ("type", OrderedDict([
            ("tag", "BVType"), ("args", [32, "LittleEndian"]),
        ])),
        ("expression", OrderedDict([
            ("tag", "BVLiteral"), ("width", 32),
            ("exactWidthBits", "0" * 32),
            ("sort", OrderedDict([("tag", "BV"), ("args", [32])])),
        ])),
        ("occurrenceGuard", OrderedDict([
            ("tag", "BoolLiteral"), ("value", True),
            ("sort", OrderedDict([("tag", "Bool")])),
        ])),
        ("audience", OrderedDict([
            ("worldVisible", True), ("memberVisible", []),
            ("minimallyJointVisible", []),
        ])),
        ("footprint", [OrderedDict([
            ("tag", "ReleasePayloadByteV2"), ("args", [0]),
        ])]),
        ("multiplicity", OrderedDict([
            ("tag", "NatLiteral"), ("value", 1), ("max", 1),
            ("sort", OrderedDict([("tag", "Nat"), ("args", [1])])),
        ])),
        ("activationClaims", [OrderedDict([
            ("key", "entry.main"),
            ("value", OrderedDict([("tag", "RequiredReachable")])),
        ])]),
        ("deterministicSemantics", policy_semantics_version()),
    ])


def release_table() -> OrderedDict[str, Any]:
    return OrderedDict([
        ("formatId", "SPS-ReleaseTable-v2"),
        ("expressionSemantics", policy_semantics_version()),
        ("entries", [release_spec()]),
    ])


TRANSITION_RULE_IDS = [
    "IntBinaryTotalV2", "IntDivRemPartialV2", "ShiftPartialV2",
    "IntegerCompareV2", "PointerEqualityV2", "IntegerCastV2", "BitcastV2",
    "FNegBitsV2", "FCmpBitsV2", "PhiEdgeAssignmentV2", "SelectV2", "GEPV2",
    "AllocaV2", "LoadV2", "StoreV2", "BranchV2", "SwitchV2",
    "BoundRemainderV2", "InternalCallV2", "ContractCallV2",
    "ReleaseBoundaryV2", "HelperReturnV2", "EntryReturnV2", "UnreachableV2",
    "DebugNoOpV2",
]


def canonical_payload(field_name: str) -> OrderedDict[str, Any]:
    if field_name == "llvmBuild":
        return OrderedDict([
            ("repository", "https://github.com/llvm/llvm-project"),
            ("tag", "llvmorg-22.1.8"),
            ("commit", "ca7933e47d3a3451d81e72ac174dcb5aa28b59d1"),
            ("compilerBinaryDigest", ZERO), ("libraryDigests", []),
        ])
    if field_name == "spsBuild":
        return OrderedDict([
            ("patchCommit", "0" * 40), ("verifierCoreBinaryDigest", ZERO),
            ("normalizerId", "SPSFinalWeaken_v2"),
            ("normalizerBinaryDigest", ZERO), ("normalizerOptions", []),
            ("auditorId", "sps.nfv2.audit"), ("auditorBinaryDigest", ZERO),
            ("transitionRuleTableDigest", canonical_input("transitionRuleTable")["sha256"]),
        ])
    if field_name == "passTrace":
        return OrderedDict([
            ("rows", [OrderedDict([
                ("ordinal", 0), ("passId", "SPSFinalWeaken_v2"),
                ("implementationDigest", ZERO),
                ("pluginDigest", OrderedDict([("tag", "None")])),
                ("options", []), ("mutatesIR", True),
            ])]),
            ("freezeCoordinate", OrderedDict([
                ("llvmCommit", "ca7933e47d3a3451d81e72ac174dcb5aa28b59d1"),
                ("targetPassConfigConcreteClass", "fixture.TargetPassConfig"),
                ("instructionSelector", "SelectionDAG"),
            ])),
        ])
    if field_name == "targetConfiguration":
        return OrderedDict([
            ("targetTriple", "x86_64-unknown-linux-gnu"), ("dataLayout", "e-p:64:64"),
            ("targetCPU", "x86-64"), ("targetFeatures", []), ("tuneCPU", "generic"),
            ("relocationModel", "Static"), ("codeModel", "Small"),
            ("codegenOptimizationLevel", "Default"), ("floatABI", "Default"),
            ("instructionSelector", "SelectionDAG"), ("fastISelEnabled", False),
            ("globalISelEnabled", False), ("globalISelFallbackEnabled", False),
            ("ltoMode", "complete-before-freeze"), ("sanitizerMode", "none"),
            ("canonicalBitcodeWriterOptions", []),
        ])
    if field_name == "abi":
        return OrderedDict([
            ("abiId", ZERO), ("targetDataLayout", "e-p:64:64"),
            ("entries", [OrderedDict([
                ("key", "entry.main"),
                ("value", OrderedDict([
                    ("functionType", "void (i32)"), ("roots", []),
                    ("returnObservationHost", "host.fixture"),
                    ("returnBitWidth", [OrderedDict([
                        ("key", OrderedDict([("tag", "NormalVoid")])), ("value", 0),
                    ])]),
                    ("declaredErrorFields", ["error.ub-risk"]),
                ])),
            ])]),
            ("carriers", [OrderedDict([
                ("key", ["entry.main", "component.high"]),
                ("value", OrderedDict([
                    ("tag", "ScalarArgumentCarrierV2"),
                    ("args", [
                        "entry.main", 0, OrderedDict([("tag", "I32")]),
                        OrderedDict([
                            ("bitWidth", 32), ("byteWidth", 4),
                            ("byteOrder", "LittleEndian"), ("highPaddingBits", 0),
                            ("signedness", "Unsigned"),
                        ]),
                    ]),
                ])),
            ])]),
            ("namedCarriers", []), ("outputBindings", []),
            ("returnClassBindings", []), ("terminalOutputOrder", []),
            ("contractEventOutputOrder", []), ("errorFields", []),
            ("ubRiskErrorFieldId", "error.ub-risk"), ("aliasTopologyBindings", []),
        ])
    if field_name == "policy":
        return OrderedDict([
            ("policyId", ZERO), ("principals", ["principal.fixture"]),
            ("hosts", ["host.fixture"]),
            ("hostVisibility", OrderedDict([
                ("worldVisible", ["host.fixture"]),
                ("memberVisible", [OrderedDict([
                    ("key", "principal.fixture"), ("value", ["host.fixture"]),
                ])]),
                ("minimallyJointVisible", []),
            ])),
            ("maximalAdversaryCoalitions", [["principal.fixture"]]),
            ("components", [OrderedDict([
                ("key", "component.high"),
                ("value", OrderedDict([
                    ("valueType", OrderedDict([("tag", "BVValueV2"), ("args", [32])])),
                    ("lifecycle", "EntryInput"),
                    ("applicableEntries", ["entry.main"]),
                ])),
            ])]),
            ("componentVisibility", OrderedDict([
                ("worldVisible", []), ("memberVisible", [OrderedDict([
                    ("key", "principal.fixture"), ("value", []),
                ])]),
                ("minimallyJointVisible", []),
            ])),
            ("outputVisibility", OrderedDict([
                ("worldVisible", []), ("memberVisible", [OrderedDict([
                    ("key", "principal.fixture"), ("value", []),
                ])]),
                ("minimallyJointVisible", []),
            ])),
            ("errorVisibility", OrderedDict([
                ("worldVisible", ["error.ub-risk"]),
                ("memberVisible", [OrderedDict([
                    ("key", "principal.fixture"), ("value", ["error.ub-risk"]),
                ])]),
                ("minimallyJointVisible", []),
            ])),
            ("entries", [OrderedDict([
                ("key", "entry.main"),
                ("value", OrderedDict([
                    ("llvmSymbol", "entry_main"),
                    ("argumentRoles", [OrderedDict([
                        ("tag", "ComponentArgumentV2"), ("args", ["component.high"]),
                    ])]),
                    ("allowedReturnClasses", [OrderedDict([("tag", "NormalVoid")])]),
                ])),
            ])]),
            ("publicBounds", []), ("preconditions", []),
            ("publicAliasTopologyIds", []), ("expectedVariableAssertions", []),
            ("allocaSizeBindings", []),
            ("releasePolicyReviewConfig", OrderedDict([
                ("capacityWarningThresholdBits", OrderedDict([
                    ("numerator", 1), ("denominator", 1),
                ])),
                ("enabledLintSet", LINT_CLASSES), ("versionAndSemantics", ZERO),
            ])),
            ("entryPlacement", [OrderedDict([("key", "entry.main"), ("value", "host.fixture")])]),
            ("releaseBindings", [OrderedDict([
                ("key", "release.one"), ("value", exact_digest(release_spec())),
            ])]),
            ("persistentInvariants", []),
            ("invocationClaim", OrderedDict([("tag", "SingleInvocation")])),
            ("contractBindings", []),
        ])
    if field_name == "contractTable":
        return OrderedDict([("formatId", "SPS-ContractTable-v2"), ("contracts", [])])
    if field_name == "placementTable":
        return OrderedDict([
            ("formatId", "SPS-FunctionPlacement-v2"), ("functionHost", []),
            ("instructionHost", []), ("globalHost", []), ("boundaryLocations", []),
        ])
    if field_name == "aliasTopology":
        return OrderedDict([
            ("formatId", "SPS-Alias-Topology-Digest-Preimage-v2"),
            ("selectedTopologyIds", []), ("bindings", []),
        ])
    if field_name == "allocaSizeBindings":
        return OrderedDict([
            ("formatId", "SPS-Alloca-Size-Bindings-Digest-Preimage-v2"),
            ("bindings", []),
        ])
    if field_name == "stableIRBindings":
        return OrderedDict((name, []) for name in [
            "functions", "blocks", "arguments", "instructions", "predecessorEdges",
            "loops", "instructionSites", "syntheticSites",
        ])
    if field_name == "transitionRuleTable":
        return OrderedDict([
            ("formatId", "SPS-TransitionRules-v2"), ("llvmVersion", "22.1.8"),
            ("ruleIds", TRANSITION_RULE_IDS),
        ])
    if field_name == "observationSemantics":
        return OrderedDict([
            ("addressMode", "StableAllocationExactByteOffsetV2"),
            ("dynamicOccurrenceMode", "SitePrefixSumWithinStepOrdinalV2"),
            ("eventSchema", "Theta-ct-Events-v2"),
            ("projectionSchema", "SPS-CoalitionProjection-v2"),
            ("transferMetadataPolicy", "EmptyTransferMetadataV2"),
            ("staticArtifactBoundary", "WorldPublicStaticArtifactsV2"),
        ])
    if field_name == "latencyClassTable":
        return OrderedDict([("siteSchemas", []), ("rows", [])])
    if field_name == "timingEnvironment":
        return OrderedDict([
            ("timingEnvironmentId", ZERO), ("choiceDomain", []),
            ("occurrences", []), ("latencyMeaning", []),
            ("latencyClasses", [OrderedDict([("latencyClassId", "latency.zero")])]),
            ("pairedChoiceCoupling", []), ("versionAndObservationBoundary", ZERO),
        ])
    if field_name == "stackProtectorPreflight":
        return OrderedDict([("sspSites", []), ("sspStrongSites", []), ("sspReqSites", [])])
    if field_name == "fpNaNPayloadSemantics":
        return OrderedDict([("formatId", "SPS-FP-NaN-Payload-Semantics-v2"), ("rules", [])])
    if field_name == "policyReviewConfiguration":
        return OrderedDict([
            ("capacityWarningThresholdBits", OrderedDict([("numerator", 1), ("denominator", 1)])),
            ("enabledLintSet", LINT_CLASSES), ("versionAndSemantics", ZERO),
        ])
    if field_name == "entryScope":
        return OrderedDict([("rows", [OrderedDict([
            ("entryId", "entry.main"), ("entryFunctionId", "function.entry.main"),
            ("reachableFunctionIds", ["function.entry.main", "wrapper.release.one"]),
            ("reachableBoundaryIds", []), ("reachableReleaseIds", ["release.one"]),
        ])])])
    if field_name == "profileConfiguration":
        return OrderedDict([
            ("globalRegionTableDigest", canonical_input("globalRegionTable")["sha256"]),
            ("preflightTaskScheduleDigest", canonical_input("preflightTaskSchedule")["sha256"]),
            ("integerWidths", [1, 8, 16, 32, 64]), ("floatTypes", ["float", "double"]),
            ("maxVectorLanesBeforeNormalization", 1), ("loopBoundBindings", []),
            ("allocaSizeBindings", []),
            ("publicAliasTopologyDigest", canonical_input("aliasTopology")["sha256"]),
            ("enginePathCap", 4096), ("engineByteCap", 1048576),
            ("moduleFlagPolicy", "RejectAllModuleFlagsV2"),
            ("codegenAttributePolicy", "ClosedAttributeClassesOnlyV2"),
            ("stackProtectorPolicy", "ForbidSSPFamilyV2"),
        ])
    if field_name == "publicBounds":
        return OrderedDict([("formatId", "SPS-Public-Bounds-Digest-Preimage-v2"), ("bounds", [])])
    if field_name == "preconditions":
        return OrderedDict([("formatId", "SPS-Preconditions-Digest-Preimage-v2"), ("predicates", [])])
    if field_name == "policyExpressionSemantics":
        return policy_semantics_version()
    if field_name == "ponfSemantics":
        return OrderedDict([
            ("formatId", "SPS-PONF-v2"), ("operatorTableVersion", "v2"),
            ("stateEncodingVersion", "v2"),
            ("memoryEncodingVersion", "single-pair-array-v2"),
            ("couplingEncodingVersion", "v2"),
            ("ledgerEncodingVersion", "prefix-ledger-v2"),
            ("queryTableVersion", "v2"),
        ])
    if field_name == "globalRegionTable":
        return OrderedDict([("rows", [])])
    if field_name == "preflightTaskSchedule":
        return OrderedDict([("formatId", "SPS-Preflight-Task-Schedule-v2"), ("tasks", [])])
    raise KeyError(field_name)


def canonical_input(field_name: str) -> OrderedDict[str, Any]:
    if field_name in UNCHANGED_IDENTITY_INPUTS:
        record_name, format_id, _ = UNCHANGED_IDENTITY_INPUTS[field_name]
    else:
        record_name, format_id = AUXILIARY_CONFORMANCE_INPUTS[field_name]
    if field_name == "releaseTable":
        value: Any = release_table()
    elif field_name == "interfaceManifest":
        value = conformance_interface_manifest()
    else:
        value = canonical_payload(field_name)
    raw = canonical_bytes(value)
    return OrderedDict([
        ("formatId", format_id), ("canonicalBytes", raw.hex()), ("sha256", sha256(raw)),
    ])


def release_marker_bindings() -> OrderedDict[str, Any]:
    spec = release_spec()
    return OrderedDict([
        ("formatId", "SPS-Release-Marker-Bindings-v2"),
        ("releaseTableFormatId", "SPS-ReleaseTable-v2"),
        ("intrinsicName", "llvm.sps.release"),
        ("rows", [OrderedDict([
            ("releaseId", "release.one"), ("siteId", "site.release.one"),
            ("implementation", OrderedDict([
                ("wrapperFunction", "wrapper.release.one"),
                ("emitMarkerInstructionId", "inst.release.one"),
            ])),
            ("flattenedIntegerWidths", [32]),
            ("releaseSpecV2Digest", sha256(canonical_bytes(spec))),
        ])]),
    ])


def release_marker_machine_map() -> OrderedDict[str, Any]:
    return OrderedDict([
        ("formatId", "SPS-Release-Marker-Machine-Map-v2"),
        ("rows", [OrderedDict([
            ("emitMarkerInstructionId", "inst.release.one"),
            ("mirPseudoId", "mir.release.one"),
            ("p4BoundaryId", "p4.release.one"),
        ])]),
    ])


def identity_evidence() -> OrderedDict[str, Any]:
    canonical_inputs = OrderedDict(
        (field_name, canonical_input(field_name))
        for field_name in [*UNCHANGED_IDENTITY_INPUTS, *AUXILIARY_CONFORMANCE_INPUTS]
    )
    bitcode_raw = b"BC\xc0\xdeSPS-NFv2"
    bitcode = OrderedDict([
        ("formatId", "SPS-Canonical-Bitcode-v2"),
        ("exactBytes", bitcode_raw.hex()), ("sha256", sha256(bitcode_raw)),
    ])
    proof = proof_configuration(canonical_inputs=canonical_inputs)
    schedule_derivation = query_schedule_derivation(canonical_inputs, proof)
    bindings = release_marker_bindings()
    machine_map = release_marker_machine_map()
    intrinsic = intrinsic_definition()
    aggregation = aggregation_semantics()
    replay = replay_acceptance_semantics()
    identity = OrderedDict([
        ("formatId", "SPS-ArtifactIdentity-v2"),
        ("profileId", "SPS-LLVM-NF-v2"),
        ("normalFormVersion", "SPS-LLVM-NF-v2"),
        ("finalWeakenerId", "SPSFinalWeaken_v2"),
        ("releaseTableFormatId", "SPS-ReleaseTable-v2"),
        ("releaseMarkerBindingsFormatId", "SPS-Release-Marker-Bindings-v2"),
        ("releaseMarkerMachineMapFormatId", "SPS-Release-Marker-Machine-Map-v2"),
        ("aggregationSemanticsId", "SPS-Model-Aggregation-v2"),
        ("replayAcceptanceSemanticsId", "SPS-Replay-Acceptance-v2"),
        ("canonicalBitcodeHash", bitcode["sha256"]),
    ])
    for field_name, (_, _, identity_field) in UNCHANGED_IDENTITY_INPUTS.items():
        if identity_field != "interfaceManifestDigest":
            identity[identity_field] = canonical_inputs[field_name]["sha256"]
    identity["proofConfigurationDigest"] = sha256(canonical_bytes(proof))
    identity["queryScheduleDerivationDigest"] = sha256(canonical_bytes(schedule_derivation))
    identity["releaseMarkerBindingsDigest"] = sha256(canonical_bytes(bindings))
    identity["releaseMarkerMachineMapDigest"] = sha256(canonical_bytes(machine_map))
    identity["intrinsicDefinitionDigest"] = sha256(canonical_bytes(intrinsic))
    identity["interfaceManifestDigest"] = canonical_inputs["interfaceManifest"]["sha256"]
    identity["aggregationSemanticsDigest"] = sha256(canonical_bytes(aggregation))
    identity["replayAcceptanceSemanticsDigest"] = sha256(canonical_bytes(replay))
    evidence = OrderedDict([
        ("formatId", "SPS-Artifact-Identity-Evidence-v2"),
        ("profileId", "SPS-LLVM-NF-v2"),
        ("artifactIdentityDigest", sha256(canonical_bytes(identity))),
        ("artifactIdentity", identity),
        ("canonicalBitcode", bitcode),
    ])
    evidence.update(canonical_inputs)
    evidence["proofConfiguration"] = proof
    evidence["queryScheduleDerivation"] = schedule_derivation
    evidence["releaseMarkerBindings"] = bindings
    evidence["releaseMarkerMachineMap"] = machine_map
    evidence["intrinsicDefinition"] = intrinsic
    evidence["aggregationSemantics"] = aggregation
    evidence["replayAcceptanceSemantics"] = replay
    return evidence


def nf_manifest() -> OrderedDict[str, Any]:
    evidence = identity_evidence()
    identity = evidence["artifactIdentity"]
    return OrderedDict([
        ("formatId", "SPS-LLVM-NF-Manifest-v2"),
        ("profileId", "SPS-LLVM-NF-v2"),
        ("llvmBaseline", "llvmorg-22.1.8"),
        ("llvmUpstreamCommit", "ca7933e47d3a3451d81e72ac174dcb5aa28b59d1"),
        ("intrinsicName", "llvm.sps.release"),
        ("finalWeakenerId", "SPSFinalWeaken_v2"),
        ("releaseTableFormatId", "SPS-ReleaseTable-v2"),
        ("releaseMarkerBindingsDigest", identity["releaseMarkerBindingsDigest"]),
        ("releaseMarkerMachineMapDigest", identity["releaseMarkerMachineMapDigest"]),
        ("intrinsicDefinitionDigest", identity["intrinsicDefinitionDigest"]),
        ("aggregationSemanticsDigest", identity["aggregationSemanticsDigest"]),
        ("replayAcceptanceSemanticsDigest", identity["replayAcceptanceSemanticsDigest"]),
        ("artifactIdentity", identity),
        ("artifactIdentityEvidence", evidence),
    ])


def accepted_replay(
    *, artifact_digest: str = ZERO, proof_digest: str = ONE,
    schedule_digest: str = TWO, receipt: str = ONE,
) -> OrderedDict[str, Any]:
    first_required_query = copy.deepcopy(required_query_schedule()["queries"][0])
    return OrderedDict([
        ("formatId", "SPS-Accepted-Bad-Replay-v2"),
        ("artifactIdentityDigest", artifact_digest),
        ("proofConfigurationDigest", proof_digest),
        ("queryScheduleDigest", schedule_digest),
        ("queryOrdinal", 0), ("query", first_required_query),
        ("replaySemantics", "SPS-Replay-Acceptance-v2"),
        ("firstBadStep", 3), ("firstBadStateDigest", THREE),
        ("finalReceiptId", receipt),
        ("protectedEvidence", protected(receipt)),
    ])


def aggregation_input(
    *, accepted: OrderedDict[str, Any] | None = None,
    blockers: list[OrderedDict[str, Any]] | None = None,
    gates_closed: bool = False,
    artifact_digest: str = ZERO, proof_digest: str = ONE,
    schedule_digest: str = TWO,
) -> OrderedDict[str, Any]:
    blocker_rows = sorted(blockers or [], key=canonical_bytes)
    return OrderedDict([
        ("formatId", "SPS-Aggregation-Input-v2"),
        ("artifactIdentityDigest", artifact_digest),
        ("proofConfigurationDigest", proof_digest),
        ("queryScheduleDigest", schedule_digest),
        ("acceptedBadReplay", OrderedDict([("tag", "None")]) if accepted is None
            else OrderedDict([("tag", "Some"), ("value", accepted)])),
        ("blockers", blocker_rows), ("allRequiredGatesClosed", gates_closed),
    ])


def public_report(
    *, model_status: OrderedDict[str, Any], artifact_digest: str = ZERO,
    proof_digest: str = ONE, policy_digest: str = ZERO,
    release_digest: str = ONE, policy_review_configuration_digest: str = TWO,
    preflight_task_schedule_digest: str = THREE,
    proved_results: bool = False,
) -> OrderedDict[str, Any]:
    queries = required_query_schedule()["queries"]
    schedule = OrderedDict([
        ("formatId", "SPS-Public-Query-Schedule-v2"),
        ("artifactIdentityDigest", artifact_digest),
        ("proofConfigurationDigest", proof_digest), ("queries", queries),
    ])
    query_results = []
    for ordinal, query in enumerate(queries):
        receipt = f"{100 + ordinal:064x}"
        kind = query["queryKind"]["tag"]
        existential = kind in {"AdmissionNonempty", "HighVariation", "ReleaseActivation"}
        raw_result = "SAT" if existential or not proved_results else "UNSAT"
        if existential:
            disposition = OrderedDict([("tag", "ValidatedExistentialWitness")])
        elif proved_results:
            disposition = OrderedDict([("tag", "Discharged")])
        else:
            disposition = OrderedDict([("tag", "CandidateOnly")])
        query_results.append(OrderedDict([
            ("queryOrdinal", ordinal),
            ("outcome", OrderedDict([
                ("tag", "Constructed"),
                ("args", [OrderedDict([
                    ("formatId", "SPS-PONF-Result-v2"),
                    ("canonicalPONFDigest", ZERO), ("exactFormulaDigest", ONE),
                    ("proofConfigurationDigest", proof_digest),
                    ("solver", OrderedDict([
                        ("solverName", "fixture-solver"), ("solverVersion", "1"),
                        ("solverBuildDigest", TWO), ("exactSolverOptions", []),
                        ("resourceLimits", resource_limits()),
                    ])),
                    ("rawSolverResult", raw_result),
                    ("protectedEvidence", protected(receipt)),
                    ("queryDisposition", disposition),
                ])]),
            ])),
        ]))
    policy_status = OrderedDict([("tag", "Complete")])
    policy_review = OrderedDict([
        ("formatId", "SPS-Release-Policy-Review-v2"),
        ("artifactIdentityDigest", artifact_digest),
        ("policyDigest", policy_digest), ("releaseDigest", release_digest),
        ("policyReviewConfigurationDigest", policy_review_configuration_digest),
        ("summands", []), ("totals", []), ("lints", []),
        ("status", policy_status),
    ])
    return OrderedDict([
        ("formatId", "SPS-Public-Report-v2"),
        ("profileId", "SPS-LLVM-NF-v2"),
        ("artifactIdentityFormatId", "SPS-ArtifactIdentity-v2"),
        ("artifactIdentityDigest", artifact_digest),
        ("proofConfigurationDigest", proof_digest),
        ("querySchedule", schedule),
        ("queryScheduleDigest", sha256(canonical_bytes(schedule))),
        ("queryResults", query_results),
        ("preflightTaskScheduleDigest", preflight_task_schedule_digest),
        ("preflightSummaries", []),
        ("modelStatus", model_status),
        ("deploymentStatus", OrderedDict([
            ("tag", "Open"),
            ("args", [OrderedDict([("tag", "P4EvidenceProfileUnavailable")])]),
        ])),
        ("policyReviewStatus", policy_status),
        ("releasePolicyReview", policy_review),
        ("runEvidence", protected(THREE)),
        ("statusNoninterference", "PolicyReviewDoesNotAffectModelOrDeploymentV2"),
    ])


def vector_objects() -> OrderedDict[str, tuple[str, str, Any, str | None]]:
    def replace_payload(
        evidence: OrderedDict[str, Any], field_name: str, payload: Any,
    ) -> None:
        raw = canonical_bytes(payload)
        evidence[field_name]["canonicalBytes"] = raw.hex()
        evidence[field_name]["sha256"] = sha256(raw)
        identity = evidence["artifactIdentity"]
        if field_name in UNCHANGED_IDENTITY_INPUTS:
            identity_field = UNCHANGED_IDENTITY_INPUTS[field_name][2]
            identity[identity_field] = evidence[field_name]["sha256"]
        derivation_fields = {
            "policy": "policyDigest", "abi": "abiDigest",
            "releaseTable": "releaseDigest", "contractTable": "contractDigest",
            "entryScope": "entryScopeDigest",
            "timingEnvironment": "timingEnvironmentContractDigest",
            "profileConfiguration": "profileConfigurationDigest",
        }
        if field_name in derivation_fields:
            derivation = evidence["queryScheduleDerivation"]
            derivation[derivation_fields[field_name]] = evidence[field_name]["sha256"]
            identity["queryScheduleDerivationDigest"] = exact_digest(derivation)
        identity["proofConfigurationDigest"] = exact_digest(evidence["proofConfiguration"])
        evidence["artifactIdentityDigest"] = exact_digest(identity)

    config_rejected = OrderedDict([
        ("tag", "ConfigurationRejectedV2"),
        ("report", OrderedDict([
            ("formatId", "SPS-Configuration-Rejection-v2"),
            ("disposition", "NoModelStatus"),
            ("reason", OrderedDict([("tag", "UnsupportedInterfaceVersion")])),
        ])),
    ])
    replay = accepted_replay()
    valid_proof_blocker = aggregation_input(accepted=replay, blockers=[blocker("ProofCompletion")])
    invalid_replay_blocker = aggregation_input(accepted=replay, blockers=[blocker("ReplayInvalidating")])
    proved_input = aggregation_input(gates_closed=True)
    incomplete_input = aggregation_input()
    reporting_input = aggregation_input(blockers=[blocker("RunFinalization")])
    fp_unknown_input = aggregation_input(blockers=[blocker("ReplayInvalidating")])
    multiple_blockers_input = aggregation_input(
        blockers=[blocker("ReplayInvalidating"), blocker("ProofCompletion")])

    wrong_reason = blocker("RunFinalization")
    wrong_reason["reason"] = OrderedDict([
        ("tag", "ModelBlocker"),
        ("reason", OrderedDict([("reasonClassId", "ToolInconsistency")])),
    ])
    wrong_reason_input = aggregation_input(blockers=[wrong_reason])

    bad_replay_receipt = accepted_replay()
    bad_replay_receipt["protectedEvidence"]["receiptId"] = TWO

    bad_bindings = release_marker_bindings()
    bad_bindings["rows"][0]["flattenedIntegerWidths"] = []

    bad_identity = identity_evidence()
    bad_identity["policy"]["sha256"] = ZERO

    bad_marker_evidence = identity_evidence()
    bad_marker_evidence["releaseMarkerBindings"]["rows"][0]["flattenedIntegerWidths"] = [64]
    bad_marker_identity = bad_marker_evidence["artifactIdentity"]
    bad_marker_identity["releaseMarkerBindingsDigest"] = exact_digest(
        bad_marker_evidence["releaseMarkerBindings"])
    bad_marker_evidence["artifactIdentityDigest"] = exact_digest(bad_marker_identity)

    coalition_closure_evidence = identity_evidence()
    coalition_policy = require_canonical(bytes.fromhex(
        coalition_closure_evidence["policy"]["canonicalBytes"]))
    coalition_principals = ["principal.alice", "principal.bob"]
    coalition_policy["principals"] = coalition_principals
    coalition_policy["maximalAdversaryCoalitions"] = [coalition_principals]
    for visibility_name in [
        "hostVisibility", "componentVisibility", "outputVisibility",
        "errorVisibility",
    ]:
        visibility = coalition_policy[visibility_name]
        original_member_items = visibility["memberVisible"][0]["value"]
        visibility["memberVisible"] = [OrderedDict([
            ("key", principal), ("value", copy.deepcopy(original_member_items)),
        ]) for principal in coalition_principals]
        visibility["minimallyJointVisible"] = []
    coalition_policy["componentVisibility"]["minimallyJointVisible"] = [
        [coalition_principals, "component.high"],
    ]
    coalition_policy_raw = canonical_bytes(coalition_policy)
    coalition_closure_evidence["policy"]["canonicalBytes"] = coalition_policy_raw.hex()
    coalition_closure_evidence["policy"]["sha256"] = sha256(coalition_policy_raw)
    coalition_schedule_inputs = OrderedDict(
        (field_name, coalition_closure_evidence[field_name])
        for field_name in [
            *UNCHANGED_IDENTITY_INPUTS, *AUXILIARY_CONFORMANCE_INPUTS,
        ]
    )
    coalition_proof = proof_configuration(
        canonical_inputs=coalition_schedule_inputs)
    coalition_derivation = query_schedule_derivation(
        coalition_schedule_inputs, coalition_proof)
    coalition_closure_evidence["proofConfiguration"] = coalition_proof
    coalition_closure_evidence["queryScheduleDerivation"] = coalition_derivation
    coalition_identity = coalition_closure_evidence["artifactIdentity"]
    coalition_identity["policyDigest"] = coalition_closure_evidence["policy"]["sha256"]
    coalition_identity["proofConfigurationDigest"] = exact_digest(coalition_proof)
    coalition_identity["queryScheduleDerivationDigest"] = exact_digest(
        coalition_derivation)
    coalition_closure_evidence["artifactIdentityDigest"] = exact_digest(
        coalition_identity)

    counter_status = OrderedDict([("tag", "Counterexample"), ("args", [ONE])])
    decision_evidence = identity_evidence()
    decision_identity = decision_evidence["artifactIdentity"]
    decision_artifact_digest = decision_evidence["artifactIdentityDigest"]
    decision_proof_digest = decision_identity["proofConfigurationDigest"]
    completed_report = public_report(
        model_status=counter_status,
        artifact_digest=decision_artifact_digest,
        proof_digest=decision_proof_digest,
        policy_digest=decision_identity["policyDigest"],
        release_digest=decision_identity["releaseDigest"],
        policy_review_configuration_digest=decision_identity["policyReviewConfigurationDigest"],
        preflight_task_schedule_digest=decision_evidence["preflightTaskSchedule"]["sha256"],
    )
    schedule_digest = completed_report["queryScheduleDigest"]
    decision_replay = accepted_replay(
        artifact_digest=decision_artifact_digest,
        proof_digest=decision_proof_digest,
        schedule_digest=schedule_digest,
    )
    decision_input = aggregation_input(
        accepted=decision_replay, blockers=[blocker("ProofCompletion")],
        artifact_digest=decision_artifact_digest,
        proof_digest=decision_proof_digest,
        schedule_digest=schedule_digest)
    decision = OrderedDict([
        ("formatId", "SPS-Aggregation-Decision-v2"),
        ("identityEvidence", decision_evidence),
        ("input", decision_input),
        ("runReport", OrderedDict([("tag", "CompletedV2"), ("report", completed_report)])),
    ])

    proved_report = public_report(
        model_status=OrderedDict([("tag", "Proved")]),
        artifact_digest=decision_artifact_digest,
        proof_digest=decision_proof_digest,
        policy_digest=decision_identity["policyDigest"],
        release_digest=decision_identity["releaseDigest"],
        policy_review_configuration_digest=decision_identity["policyReviewConfigurationDigest"],
        preflight_task_schedule_digest=decision_evidence["preflightTaskSchedule"]["sha256"],
        proved_results=True,
    )
    proved_schedule_digest = proved_report["queryScheduleDigest"]
    proved_decision = OrderedDict([
        ("formatId", "SPS-Aggregation-Decision-v2"),
        ("identityEvidence", copy.deepcopy(decision_evidence)),
        ("input", aggregation_input(
            gates_closed=True, artifact_digest=decision_artifact_digest,
            proof_digest=decision_proof_digest,
            schedule_digest=proved_schedule_digest)),
        ("runReport", OrderedDict([("tag", "CompletedV2"), ("report", proved_report)])),
    ])

    bad_decision_query = copy.deepcopy(decision)
    bad_decision_query["input"]["acceptedBadReplay"]["value"]["query"]["entryScope"]["value"] = "entry.other"
    bad_decision_policy = copy.deepcopy(decision)
    bad_decision_policy["runReport"]["report"]["releasePolicyReview"]["policyDigest"] = ZERO
    bad_empty_report = copy.deepcopy(proved_report)
    bad_empty_report["querySchedule"]["queries"] = []
    bad_empty_report["queryScheduleDigest"] = exact_digest(bad_empty_report["querySchedule"])
    bad_empty_report["queryResults"] = []

    bad_proved_candidate = copy.deepcopy(proved_report)
    audit_result = bad_proved_candidate["queryResults"][0]["outcome"]["args"][0]
    audit_result["rawSolverResult"] = "SAT"
    audit_result["queryDisposition"] = OrderedDict([("tag", "CandidateOnly")])

    bad_schedule_evidence = identity_evidence()
    bad_schedule_evidence["proofConfiguration"]["requiredQuerySchedule"]["queries"][0]["entryScope"]["value"] = "entry.other"
    bad_schedule_evidence["queryScheduleDerivation"]["requiredQuerySchedule"] = copy.deepcopy(
        bad_schedule_evidence["proofConfiguration"]["requiredQuerySchedule"])
    bad_schedule_identity = bad_schedule_evidence["artifactIdentity"]
    bad_schedule_identity["proofConfigurationDigest"] = exact_digest(
        bad_schedule_evidence["proofConfiguration"])
    bad_schedule_identity["queryScheduleDerivationDigest"] = exact_digest(
        bad_schedule_evidence["queryScheduleDerivation"])
    bad_schedule_evidence["artifactIdentityDigest"] = exact_digest(bad_schedule_identity)

    bad_policy_payload = identity_evidence()
    replace_payload(bad_policy_payload, "policy", OrderedDict([("bogus", True)]))
    bad_nested_policy = identity_evidence()
    nested_policy_value = require_canonical(bytes.fromhex(
        bad_nested_policy["policy"]["canonicalBytes"]))
    nested_policy_value["entries"] = [OrderedDict([("tag", "Bogus")])]
    replace_payload(bad_nested_policy, "policy", nested_policy_value)
    bad_release_payload = identity_evidence()
    release_value = require_canonical(bytes.fromhex(
        bad_release_payload["releaseTable"]["canonicalBytes"]))
    release_value["entries"][0]["expression"] = OrderedDict([("tag", "Bogus")])
    replace_payload(bad_release_payload, "releaseTable", release_value)

    bad_policy_role = identity_evidence()
    policy_role_value = require_canonical(bytes.fromhex(
        bad_policy_role["policy"]["canonicalBytes"]))
    policy_role_value["entries"][0]["value"]["argumentRoles"][0] = OrderedDict([
        ("tag", "BVValueV2"), ("args", ["component.high"]),
    ])
    replace_payload(bad_policy_role, "policy", policy_role_value)

    bad_duplicate_coalition = identity_evidence()
    duplicate_coalition_value = require_canonical(bytes.fromhex(
        bad_duplicate_coalition["policy"]["canonicalBytes"]))
    duplicate_coalition_value["maximalAdversaryCoalitions"].append(
        copy.deepcopy(duplicate_coalition_value["maximalAdversaryCoalitions"][0]))
    replace_payload(bad_duplicate_coalition, "policy", duplicate_coalition_value)

    bad_abi_carrier = identity_evidence()
    abi_carrier_value = require_canonical(bytes.fromhex(
        bad_abi_carrier["abi"]["canonicalBytes"]))
    abi_carrier_value["carriers"][0]["value"]["tag"] = "BVValueV2"
    replace_payload(bad_abi_carrier, "abi", abi_carrier_value)

    bad_abi_return_class = identity_evidence()
    abi_return_class_value = require_canonical(bytes.fromhex(
        bad_abi_return_class["abi"]["canonicalBytes"]))
    abi_return_class_value["entries"][0]["value"]["returnBitWidth"][0]["key"] = OrderedDict([
        ("tag", "I32"),
    ])
    replace_payload(bad_abi_return_class, "abi", abi_return_class_value)

    bad_placement_host = identity_evidence()
    placement_value = require_canonical(bytes.fromhex(
        bad_placement_host["placementTable"]["canonicalBytes"]))
    placement_value["functionHost"] = [OrderedDict([
        ("key", "function.main"),
        ("value", OrderedDict([("tag", "I1")])),
    ])]
    replace_payload(bad_placement_host, "placementTable", placement_value)

    bad_stable_function = identity_evidence()
    stable_value = require_canonical(bytes.fromhex(
        bad_stable_function["stableIRBindings"]["canonicalBytes"]))
    stable_value["functions"] = [OrderedDict([
        ("functionSymbol", OrderedDict([("tag", "I1")])),
    ])]
    replace_payload(bad_stable_function, "stableIRBindings", stable_value)

    bad_timing_choice = identity_evidence()
    timing_value = require_canonical(bytes.fromhex(
        bad_timing_choice["timingEnvironment"]["canonicalBytes"]))
    timing_value["choiceDomain"] = [OrderedDict([
        ("choiceId", OrderedDict([("tag", "I1")])),
    ])]
    replace_payload(bad_timing_choice, "timingEnvironment", timing_value)

    bad_entry_id = identity_evidence()
    entry_scope_value = require_canonical(bytes.fromhex(
        bad_entry_id["entryScope"]["canonicalBytes"]))
    entry_scope_value["rows"][0]["entryId"] = ""
    replace_payload(bad_entry_id, "entryScope", entry_scope_value)

    bad_duplicate_library = identity_evidence()
    llvm_value = require_canonical(bytes.fromhex(
        bad_duplicate_library["llvmBuild"]["canonicalBytes"]))
    library_row = OrderedDict([("name", "lib.fixture"), ("digest", ZERO)])
    llvm_value["libraryDigests"] = [library_row, copy.deepcopy(library_row)]
    replace_payload(bad_duplicate_library, "llvmBuild", llvm_value)

    bad_duplicate_feature = identity_evidence()
    target_value = require_canonical(bytes.fromhex(
        bad_duplicate_feature["targetConfiguration"]["canonicalBytes"]))
    target_value["targetFeatures"] = ["+sse", "+sse"]
    replace_payload(bad_duplicate_feature, "targetConfiguration", target_value)

    bad_duplicate_timing_choice = identity_evidence()
    timing_choice_value = require_canonical(bytes.fromhex(
        bad_duplicate_timing_choice["timingEnvironment"]["canonicalBytes"]))
    timing_choice_row = OrderedDict([("choiceId", "choice.fixture")])
    timing_choice_value["choiceDomain"] = [
        timing_choice_row, copy.deepcopy(timing_choice_row),
    ]
    replace_payload(bad_duplicate_timing_choice, "timingEnvironment", timing_choice_value)

    bad_duplicate_latency_schema = identity_evidence()
    latency_value = require_canonical(bytes.fromhex(
        bad_duplicate_latency_schema["latencyClassTable"]["canonicalBytes"]))
    latency_schema_row = OrderedDict([
        ("siteId", "site.fixture"), ("configurationSources", []),
        ("timingOccurrenceId", OrderedDict([("tag", "None")])),
    ])
    latency_value["siteSchemas"] = [
        latency_schema_row, copy.deepcopy(latency_schema_row),
    ]
    replace_payload(bad_duplicate_latency_schema, "latencyClassTable", latency_value)

    bad_report_digest = public_report(model_status=counter_status)
    bad_report_digest["queryScheduleDigest"] = ZERO
    bad_report_receipts = public_report(model_status=counter_status)
    reused_receipt = bad_report_receipts["queryResults"][0]["outcome"]["args"][0]["protectedEvidence"]["receiptId"]
    bad_report_receipts["runEvidence"] = protected(reused_receipt)

    stale_reason_status = OrderedDict([
        ("tag", "Unknown"),
        ("args", [OrderedDict([("reasonClassId", "ReleaseConformanceMismatch")])]),
    ])
    stage_status = OrderedDict([("tag", "NotComputed")])
    witness_status = OrderedDict([
        ("tag", "Counterexample"),
        ("args", [OrderedDict([("decodedWitness", "secret")])]),
    ])
    closed_deployment = OrderedDict([
        ("tag", "Closed"), ("args", [OrderedDict([("profile", "unsupported")])]),
    ])
    stale_query_disposition = OrderedDict([
        ("tag", "Unknown"),
        ("args", [OrderedDict([("reasonClassId", "ReleaseConformanceMismatch")])]),
    ])
    malformed_run_report = OrderedDict([
        ("tag", "CompletedV2"),
        ("report", OrderedDict([("formatId", "SPS-Public-Report-v2")])),
    ])
    return OrderedDict([
        ("canonical-valid/configuration-rejected.v2.json", ("SPSRunReportV2", "valid", config_rejected, None)),
        ("canonical-valid/nf-manifest.v2.json", ("SPSLLVMNFManifestV2", "valid", nf_manifest(), None)),
        ("canonical-valid/aggregation-decision.v2.json", ("AggregationDecisionV2", "valid", decision, None)),
        ("canonical-valid/proved-decision.v2.json", ("AggregationDecisionV2", "valid", proved_decision, None)),
        ("canonical-valid/replay-with-proof-blocker.v2.json", ("AggregationInputV2", "valid", valid_proof_blocker, None)),
        ("canonical-valid/all-gates-closed.v2.json", ("AggregationInputV2", "valid", proved_input, None)),
        ("canonical-valid/run-finalization-failure.v2.json", ("AggregationInputV2", "valid", reporting_input, None)),
        ("canonical-valid/fp-invalidating-blocker.v2.json", ("AggregationInputV2", "valid", fp_unknown_input, None)),
        ("canonical-valid/multiple-model-blockers.v2.json", ("AggregationInputV2", "valid", multiple_blockers_input, None)),
        ("canonical-valid/proof-configuration.v2.json", ("ProofConfigurationV2", "valid", proof_configuration(), None)),
        ("canonical-valid/coalition-closure-identity-evidence.v2.json", ("ArtifactIdentityEvidenceV2", "valid", coalition_closure_evidence, None)),
        ("schema-invalid/stage-status-is-not-model-status.v2.json", ("ModelStatusV2", "schema-invalid", stage_status, None)),
        ("schema-invalid/public-witness-is-not-receipt.v2.json", ("ModelStatusV2", "schema-invalid", witness_status, None)),
        ("schema-invalid/stale-release-conformance-reason.v2.json", ("ModelStatusV2", "schema-invalid", stale_reason_status, None)),
        ("schema-invalid/stale-query-disposition-reason.v2.json", ("QueryDispositionV2", "schema-invalid", stale_query_disposition, None)),
        ("schema-invalid/closed-deployment-without-v2-profile.v2.json", ("DeploymentStatusV2", "schema-invalid", closed_deployment, None)),
        ("schema-invalid/duplicate-public-reason.v2.json", ("ProofConfigurationV2", "schema-invalid", proof_configuration(duplicate_reason=True), None)),
        ("schema-invalid/malformed-run-report.v2.json", ("SPSRunReportV2", "schema-invalid", malformed_run_report, None)),
        ("semantic-invalid/replay-with-invalidating-blocker.v2.json", ("AggregationInputV2", "semantic-invalid", invalid_replay_blocker, "XF-REPLAY-001")),
        ("semantic-invalid/replay-receipt-mismatch.v2.json", ("AcceptedBadReplayV2", "semantic-invalid", bad_replay_receipt, "XF-REPLAY-002")),
        ("semantic-invalid/empty-blockers-before-gates-close.v2.json", ("AggregationInputV2", "semantic-invalid", incomplete_input, "XF-AGG-001")),
        ("semantic-invalid/wrong-blocker-reason-arm.v2.json", ("AggregationInputV2", "semantic-invalid", wrong_reason_input, "XF-AGG-002")),
        ("semantic-invalid/empty-release-payload-widths.v2.json", ("ReleaseMarkerBindingArtifactV2", "semantic-invalid", bad_bindings, "XF-INTRINSIC-001")),
        ("semantic-invalid/identity-preimage-digest-mismatch.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_identity, "XF-IDENTITY-001")),
        ("semantic-invalid/release-table-marker-width-mismatch.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_marker_evidence, "XF-INTRINSIC-001")),
        ("semantic-invalid/arbitrary-policy-payload.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_policy_payload, "XF-PAYLOAD-001")),
        ("semantic-invalid/untyped-policy-entry.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_nested_policy, "XF-PAYLOAD-001")),
        ("semantic-invalid/unknown-release-expression.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_release_payload, "XF-PAYLOAD-001")),
        ("semantic-invalid/wrong-policy-argument-role.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_policy_role, "XF-PAYLOAD-001")),
        ("semantic-invalid/duplicate-maximal-coalition.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_duplicate_coalition, "XF-PAYLOAD-001")),
        ("semantic-invalid/wrong-abi-carrier.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_abi_carrier, "XF-PAYLOAD-001")),
        ("semantic-invalid/wrong-abi-return-class.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_abi_return_class, "XF-PAYLOAD-001")),
        ("semantic-invalid/wrong-placement-host-type.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_placement_host, "XF-PAYLOAD-001")),
        ("semantic-invalid/wrong-stable-function-symbol-type.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_stable_function, "XF-PAYLOAD-001")),
        ("semantic-invalid/wrong-timing-choice-id-type.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_timing_choice, "XF-PAYLOAD-001")),
        ("semantic-invalid/invalid-entry-scope-id.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_entry_id, "XF-PAYLOAD-001")),
        ("semantic-invalid/duplicate-llvm-library.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_duplicate_library, "XF-PAYLOAD-001")),
        ("semantic-invalid/duplicate-target-feature.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_duplicate_feature, "XF-PAYLOAD-001")),
        ("semantic-invalid/duplicate-timing-choice.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_duplicate_timing_choice, "XF-PAYLOAD-001")),
        ("semantic-invalid/duplicate-latency-site-schema.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_duplicate_latency_schema, "XF-PAYLOAD-001")),
        ("semantic-invalid/schedule-not-derived-from-inputs.v2.json", ("ArtifactIdentityEvidenceV2", "semantic-invalid", bad_schedule_evidence, "XF-IDENTITY-001")),
        ("semantic-invalid/report-schedule-digest-mismatch.v2.json", ("SPSPublicReportV2", "semantic-invalid", bad_report_digest, "XF-REPORT-003")),
        ("semantic-invalid/report-receipt-reuse.v2.json", ("SPSPublicReportV2", "semantic-invalid", bad_report_receipts, "XF-REPORT-002")),
        ("semantic-invalid/replay-query-mismatch.v2.json", ("AggregationDecisionV2", "semantic-invalid", bad_decision_query, "XF-REPLAY-002")),
        ("semantic-invalid/report-policy-identity-mismatch.v2.json", ("AggregationDecisionV2", "semantic-invalid", bad_decision_policy, "XF-REPORT-003")),
        ("semantic-invalid/empty-authenticated-query-schedule.v2.json", ("SPSPublicReportV2", "semantic-invalid", bad_empty_report, "XF-REPORT-003")),
        ("semantic-invalid/proved-with-candidate-only.v2.json", ("SPSPublicReportV2", "semantic-invalid", bad_proved_candidate, "XF-REPORT-003")),
    ])


RAW_CASES = [
    ("canonical-proved", "ModelStatusV2", b'{"tag":"Proved"}', "valid"),
    ("trailing-lf", "ModelStatusV2", b'{"tag":"Proved"}\n', "canonical-invalid"),
    ("insignificant-space", "ModelStatusV2", b'{"tag": "Proved"}', "canonical-invalid"),
    ("non-shortest-unicode-escape", "ModelStatusV2", b'{"tag":"Pro\\u0076ed"}', "canonical-invalid"),
    ("duplicate-key", "ModelStatusV2", b'{"tag":"Proved","tag":"Proved"}', "parse-invalid"),
    ("utf8-bom", "ModelStatusV2", b'\xef\xbb\xbf{"tag":"Proved"}', "parse-invalid"),
    ("lone-surrogate", "ModelStatusV2", b'{"tag":"\\ud800"}', "parse-invalid"),
    ("tag-not-first", "ModelStatusV2", b'{"args":[],"tag":"Proved"}', "schema-invalid"),
    ("negative-zero", "BlockerRecordV2", b'{"formatId":"SPS-Blocker-Record-v2","scope":"ProofCompletion","phaseOrdinal":-0,"scheduleOrdinal":{"tag":"None"},"reason":{"reasonClassId":"SolverTimeout"},"restrictedDetailDigest":"' + b'0' * 64 + b'"}', "canonical-invalid"),
    ("float-exponent", "BlockerRecordV2", b'{"formatId":"SPS-Blocker-Record-v2","scope":"ProofCompletion","phaseOrdinal":1e0,"scheduleOrdinal":{"tag":"None"},"reason":{"reasonClassId":"SolverTimeout"},"restrictedDetailDigest":"' + b'0' * 64 + b'"}', "parse-invalid"),
    ("nan", "BlockerRecordV2", b'{"formatId":"SPS-Blocker-Record-v2","scope":"ProofCompletion","phaseOrdinal":NaN,"scheduleOrdinal":{"tag":"None"},"reason":{"reasonClassId":"SolverTimeout"},"restrictedDetailDigest":"' + b'0' * 64 + b'"}', "parse-invalid"),
]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strict_load(raw: bytes) -> Any:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid UTF-8") from exc

    def pairs(rows: list[tuple[str, Any]]) -> OrderedDict[str, Any]:
        result: OrderedDict[str, Any] = OrderedDict()
        for key, value in rows:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    def bad_constant(value: str) -> Any:
        raise ValueError(f"forbidden numeric constant: {value}")

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_float=lambda _: (_ for _ in ()).throw(ValueError("floats are forbidden")), parse_constant=bad_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid canonical JSON: {exc}") from exc
    return value


def require_canonical(raw: bytes) -> Any:
    value = strict_load(raw)
    try:
        rebuilt = canonical_bytes(value)
    except UnicodeError as exc:
        raise ValueError("JSON string contains a non-scalar Unicode value") from exc
    if rebuilt != raw:
        raise ValueError("bytes are not CanonInterfaceJSONV2")
    return value


ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$")
HEX_RE = re.compile(r"^[0-9a-f]{64}$")
BYTES_RE = re.compile(r"^(?:[0-9a-f]{2})*$")


def validate_descriptor(value: Any, desc: dict[str, Any], where: str = "$") -> None:
    kind = desc["kind"]
    if kind in {"digest", "receipt"}:
        if not isinstance(value, str) or not HEX_RE.fullmatch(value):
            raise ValueError(f"{where}: expected 256-bit lowercase hex")
    elif kind == "hex":
        if not isinstance(value, str) or not BYTES_RE.fullmatch(value):
            raise ValueError(f"{where}: expected lowercase exact-byte hex")
    elif kind == "id":
        if not isinstance(value, str) or not ID_RE.fullmatch(value):
            raise ValueError(f"{where}: invalid stable identifier")
    elif kind == "nat":
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{where}: expected natural")
    elif kind == "pos":
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{where}: expected positive natural")
    elif kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{where}: expected boolean")
    elif kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"{where}: expected string")
    elif kind == "literal":
        if value != desc["value"] or type(value) is not type(desc["value"]):
            raise ValueError(f"{where}: expected literal {desc['value']!r}")
    elif kind == "enum":
        values = ENUMS[desc["name"]]["values"]
        if value not in values:
            raise ValueError(f"{where}: not in {desc['name']}")
    elif kind == "record":
        validate_record(value, desc["name"], where)
    elif kind == "union":
        validate_union(value, desc["name"], where)
    elif kind == "list":
        if not isinstance(value, list):
            raise ValueError(f"{where}: expected list")
        for index, item in enumerate(value):
            validate_descriptor(item, desc["item"], f"{where}[{index}]")
        if desc.get("unique"):
            encoded = [canonical_bytes(item) for item in value]
            if len(encoded) != len(set(encoded)):
                raise ValueError(f"{where}: canonical unique list is duplicated")
            if desc.get("order") == "QueryKindV2":
                expected = [OrderedDict([("tag", item)]) for item in QUERY_KINDS]
                if value != expected:
                    raise ValueError(f"{where}: query-kind normative order mismatch")
            elif desc.get("order") == "PublicReasonClassesV2":
                if value != PUBLIC_REASONS_V2:
                    raise ValueError(f"{where}: PublicReasonClassesV2 normative order mismatch")
            elif desc.get("order") == "canonical-element-bytes" and encoded != sorted(encoded):
                raise ValueError(f"{where}: canonical unique list is unsorted or duplicated")
            elif desc.get("order") == "manifest-path":
                paths = [item["path"] for item in value]
                if paths != sorted(paths) or len(paths) != len(set(paths)):
                    raise ValueError(f"{where}: manifest paths are unsorted or duplicated")
    elif kind == "option":
        if not isinstance(value, dict) or list(value) not in (["tag"], ["tag", "value"]):
            raise ValueError(f"{where}: malformed option")
        if value["tag"] == "None" and list(value) == ["tag"]:
            return
        if value["tag"] == "Some" and list(value) == ["tag", "value"]:
            validate_descriptor(value["value"], desc["item"], where + ".value")
            return
        raise ValueError(f"{where}: malformed option arm")
    elif kind == "choice":
        matches = 0
        for item in desc["items"]:
            try:
                validate_descriptor(value, item, where)
            except ValueError:
                continue
            matches += 1
        if matches != 1:
            raise ValueError(f"{where}: expected exactly one closed scalar choice")
    else:
        raise AssertionError(kind)


def validate_record(value: Any, name: str, where: str = "$") -> None:
    rows = RECORDS[name]
    expected = [row["name"] for row in rows]
    if not isinstance(value, dict) or list(value) != expected:
        actual = list(value) if isinstance(value, dict) else type(value).__name__
        raise ValueError(f"{where}: {name} fields/order {actual}, expected {expected}")
    for row in rows:
        validate_descriptor(value[row["name"]], row["type"], where + "." + row["name"])


def validate_union(value: Any, name: str, where: str = "$") -> None:
    if not isinstance(value, dict) or not value or list(value)[0] != "tag" or not isinstance(value.get("tag"), str):
        raise ValueError(f"{where}: {name} must be a tag-first object")
    variants = {variant["tag"]: variant for variant in UNIONS[name]}
    if value["tag"] not in variants:
        raise ValueError(f"{where}: unknown {name} tag {value['tag']!r}")
    variant = variants[value["tag"]]
    if variant["shape"] == "nullary":
        if list(value) != ["tag"]:
            raise ValueError(f"{where}: nullary arm has extra fields")
    elif variant["shape"] == "args":
        if list(value) != ["tag", "args"] or not isinstance(value["args"], list) or len(value["args"]) != len(variant["args"]):
            raise ValueError(f"{where}: malformed positional arm")
        for index, desc in enumerate(variant["args"]):
            validate_descriptor(value["args"][index], desc, f"{where}.args[{index}]")
    else:
        rows = variant["fields"]
        expected = ["tag"] + [row["name"] for row in rows]
        if list(value) != expected:
            raise ValueError(f"{where}: field arm order mismatch")
        for row in rows:
            validate_descriptor(value[row["name"]], row["type"], where + "." + row["name"])


def validate_root(value: Any, root: str) -> None:
    if root in RECORDS:
        validate_record(value, root)
    elif root in UNIONS:
        validate_union(value, root)
    else:
        raise ValueError(f"unknown root type: {root}")


def append_failure(failures: list[str], rule: str) -> None:
    if rule not in failures:
        failures.append(rule)


def exact_digest(value: Any) -> str:
    return sha256(canonical_bytes(value))


def envelope_is_exact(value: Any) -> bool:
    try:
        raw = bytes.fromhex(value["canonicalBytes"])
        require_canonical(raw)
    except (KeyError, TypeError, ValueError):
        return False
    return sha256(raw) == value["sha256"]


EXACT_CANONICAL_PAYLOADS = {
    "transitionRuleTable", "observationSemantics", "fpNaNPayloadSemantics",
    "policyExpressionSemantics", "ponfSemantics", "interfaceManifest",
}


POLICY_EXPR_FIELDS = {
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
        "tag", "elements", "elementSignedness", "iterationOrder", "tieRule",
        "resultWidth", "sort",
    ],
}
for _tag in ["Not", "BVNot"]:
    POLICY_EXPR_FIELDS[_tag] = ["tag", "operand", "sort"]
for _tag in ["And", "Or"]:
    POLICY_EXPR_FIELDS[_tag] = ["tag", "operands", "sort"]
for _tag in [
    "Xor", "BVAnd", "BVOr", "BVXor", "BVAddWrap", "BVSubWrap", "BVMulWrap",
    "BoolEqual", "BVEqual", "TagEqual", "TupleEqual",
]:
    POLICY_EXPR_FIELDS[_tag] = ["tag", "lhs", "rhs", "sort"]
POLICY_EXPR_FIELDS["Concat"] = ["tag", "high", "low", "sort"]
for _tag in ["NatAddChecked", "NatMulChecked"]:
    POLICY_EXPR_FIELDS[_tag] = ["tag", "lhs", "rhs", "resultMax", "sort"]
POLICY_EXPR_FIELDS["BVCompare"] = ["tag", "predicate", "signedness", "lhs", "rhs", "sort"]
POLICY_EXPR_FIELDS["NatCompare"] = ["tag", "predicate", "lhs", "rhs", "sort"]

def typed_nat(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def typed_pos(value: Any) -> bool:
    return typed_nat(value) and value > 0


def typed_id(value: Any) -> bool:
    return isinstance(value, str) and ID_RE.fullmatch(value) is not None


def typed_digest(value: Any) -> bool:
    return isinstance(value, str) and HEX_RE.fullmatch(value) is not None


def typed_tag(value: Any, tag: str) -> bool:
    return isinstance(value, dict) and list(value) == ["tag"] and value["tag"] == tag


def typed_args(value: Any, tag: str, predicates: list[Any]) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["tag", "args"]
        and value["tag"] == tag and isinstance(value["args"], list)
        and len(value["args"]) == len(predicates)
        and all(predicate(item) for predicate, item in zip(predicates, value["args"]))
    )


def typed_option(value: Any, predicate: Any) -> bool:
    return typed_tag(value, "None") or (
        isinstance(value, dict) and list(value) == ["tag", "value"]
        and value["tag"] == "Some" and predicate(value["value"])
    )


def typed_id_list(value: Any, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list) and (not nonempty or bool(value))
        and all(typed_id(item) for item in value)
        and value == sorted(value) and len(value) == len(set(value))
    )


def typed_canonical_unique_list(value: Any, *, nonempty: bool = False) -> bool:
    if not isinstance(value, list) or (nonempty and not value):
        return False
    encoded = [canonical_bytes(item) for item in value]
    return encoded == sorted(encoded) and len(encoded) == len(set(encoded))


def typed_unique_list(value: Any, *, nonempty: bool = False) -> bool:
    if not isinstance(value, list) or (nonempty and not value):
        return False
    encoded = [canonical_bytes(item) for item in value]
    return len(encoded) == len(set(encoded))


def typed_map_rows(rows: Any, key_predicate: Any, value_predicate: Any) -> bool:
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


def typed_policy_sort(value: Any) -> bool:
    if typed_tag(value, "Bool"):
        return True
    if typed_args(value, "Nat", [typed_nat]) or typed_args(value, "BV", [typed_pos]):
        return True
    if typed_args(value, "FiniteTag", [typed_id]):
        return True
    return typed_args(value, "Tuple", [
        lambda items: isinstance(items, list) and bool(items)
        and all(typed_policy_sort(item) for item in items)
    ])


def typed_nat_sort(value: Any) -> bool:
    return typed_args(value, "Nat", [typed_nat])


def typed_relation_field_path(value: Any) -> bool:
    if any(typed_tag(value, tag) for tag in [
        "ContractInputUnitV2", "ContractOutcomeV2", "CouplingOccurrenceV2",
        "CouplingChoiceV2",
    ]):
        return True
    nested = lambda item: isinstance(item, list) and all(typed_nat(part) for part in item)
    whole = lambda item: typed_tag(item, "WholeValueV2")
    return any([
        typed_args(value, "ContractArgumentV2", [typed_nat, nested, whole]),
        typed_args(value, "ContractPreStateV2", [nested]),
        typed_args(value, "ContractPreEffectByteV2", [typed_nat, typed_nat]),
        typed_args(value, "ContractResultV2", [nested]),
        typed_args(value, "ContractPostStateV2", [nested]),
        typed_args(value, "ContractPostEffectByteV2", [typed_nat, typed_nat]),
        typed_args(value, "ContractMetadataV2", [typed_id, nested]),
        typed_args(value, "ContractFailurePayloadV2", [typed_id, nested]),
    ])


def typed_policy_expr(value: Any) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("tag"), str):
        return False
    tag = value["tag"]
    if tag not in POLICY_EXPR_FIELDS or list(value) != POLICY_EXPR_FIELDS[tag]:
        return False
    if not typed_policy_sort(value["sort"]):
        return False
    expression = typed_policy_expr
    if tag == "BoolLiteral":
        return isinstance(value["value"], bool)
    if tag == "NatLiteral":
        return typed_nat(value["value"]) and typed_nat(value["max"]) and value["value"] <= value["max"]
    if tag == "BVLiteral":
        bits = value["exactWidthBits"]
        return typed_pos(value["width"]) and isinstance(bits, str) and re.fullmatch(r"[01]+", bits) is not None and len(bits) == value["width"]
    if tag == "FiniteTagLiteral":
        return typed_id(value["domainId"]) and typed_id(value["memberId"])
    if tag == "ComponentRef":
        return typed_id(value["componentId"]) and value["snapshot"] == "EntryInitial"
    if tag == "PublicBoundRef":
        return typed_id(value["boundId"])
    if tag == "OccurrenceCounterRef":
        return typed_id(value["releaseOrTimingId"])
    if tag == "RelationFieldRef":
        return value["side"] in {"Left", "Right"} and typed_relation_field_path(value["fieldPath"])
    if tag == "TupleExpr":
        return isinstance(value["fieldExprs"], list) and bool(value["fieldExprs"]) and all(expression(item) for item in value["fieldExprs"])
    if tag == "Project":
        return expression(value["tupleExpr"]) and typed_nat(value["fieldIndex"])
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
        return expression(value["operand"]) and typed_nat(value["highInclusive"]) and typed_nat(value["lowInclusive"])
    if tag in {"ZeroExtend", "SignExtend", "TruncateLow"}:
        return expression(value["operand"]) and typed_pos(value["resultWidth"])
    if tag in {"NatAddChecked", "NatMulChecked"}:
        return expression(value["lhs"]) and expression(value["rhs"]) and typed_nat(value["resultMax"])
    if tag == "ArgMax":
        return (
            isinstance(value["elements"], list) and bool(value["elements"])
            and all(expression(item) for item in value["elements"])
            and value["elementSignedness"] in {"Unsigned", "SignedTwosComplement"}
            and value["iterationOrder"] == "IncreasingIndex"
            and value["tieRule"] == "LowestIndex" and typed_pos(value["resultWidth"])
        )
    return False


def validate_policy_expression_grammar() -> None:
    bv8 = OrderedDict([("tag", "BV"), ("args", [8])])
    bv26 = OrderedDict([("tag", "BV"), ("args", [16])])
    literal = lambda bits: OrderedDict([
        ("tag", "BVLiteral"), ("width", 8), ("exactWidthBits", bits),
        ("sort", copy.deepcopy(bv8)),
    ])
    valid_concat = OrderedDict([
        ("tag", "Concat"), ("high", literal("00000000")),
        ("low", literal("11111111")), ("sort", bv26),
    ])
    invalid_concat = OrderedDict([
        ("tag", "Concat"), ("lhs", literal("00000000")),
        ("rhs", literal("11111111")), ("sort", copy.deepcopy(bv26)),
    ])
    if not typed_policy_expr(valid_concat) or typed_policy_expr(invalid_concat):
        raise ValueError("PolicyExpr Concat field grammar self-check failed")


def typed_manifest_value_type(value: Any) -> bool:
    if typed_tag(value, "BoolValueV2"):
        return True
    if typed_args(value, "BVValueV2", [typed_pos]) or typed_args(value, "FixedBytesValueV2", [typed_pos]):
        return True
    return typed_args(value, "TupleValueV2", [
        lambda fields: isinstance(fields, list) and bool(fields)
        and all(
            isinstance(field, list) and len(field) == 2 and typed_id(field[0])
            and typed_manifest_value_type(field[1])
            for field in fields
        )
        and len({field[0] for field in fields}) == len(fields)
    ])


def typed_return_class(value: Any) -> bool:
    return (
        typed_tag(value, "NormalVoid") or typed_tag(value, "NormalValue")
        or typed_args(value, "DeclaredFailure", [typed_id])
    )


def typed_argument_role(value: Any) -> bool:
    return any(typed_args(value, tag, [typed_id]) for tag in [
        "ComponentArgumentV2", "PointerRootArgumentV2",
        "PublicConfigurationArgumentV2",
    ])


def typed_bit_encoding(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["bitWidth", "byteWidth", "byteOrder", "highPaddingBits", "signedness"]
        and typed_pos(value["bitWidth"]) and typed_pos(value["byteWidth"])
        and value["byteOrder"] in {"LittleEndian", "BigEndian"}
        and typed_nat(value["highPaddingBits"]) and value["highPaddingBits"] < 8
        and value["signedness"] in {"Unsigned", "SignedTwosComplement", "NotNumeric"}
        and value["byteWidth"] == (value["bitWidth"] + 7) // 8
        and value["highPaddingBits"] == 8 * value["byteWidth"] - value["bitWidth"]
    )


def typed_root_slice(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["rootId", "byteOffset", "byteWidth"]
        and typed_id(value["rootId"]) and typed_nat(value["byteOffset"])
        and typed_pos(value["byteWidth"])
    )


def typed_scalar_type(value: Any) -> bool:
    return any(typed_tag(value, tag) for tag in ["I1", "I8", "I16", "I32", "I64", "F32", "F64"])


def typed_carrier(value: Any) -> bool:
    return any([
        typed_args(value, "ScalarArgumentCarrierV2", [typed_id, typed_nat, typed_scalar_type, typed_bit_encoding]),
        typed_args(value, "RootSliceCarrierV2", [typed_id, typed_root_slice, typed_bit_encoding, lambda item: item == "EntryInitial"]),
        typed_args(value, "GlobalSliceCarrierV2", [typed_id, typed_id, typed_nat, typed_pos, typed_bit_encoding, lambda item: item == "EntryInitial"]),
    ])


def typed_visibility(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["worldVisible", "memberVisible", "minimallyJointVisible"]
        and typed_id_list(value["worldVisible"])
        and typed_map_rows(value["memberVisible"], typed_id, typed_id_list)
        and isinstance(value["minimallyJointVisible"], list)
        and typed_canonical_unique_list(value["minimallyJointVisible"])
        and all(
            isinstance(row, list) and len(row) == 2
            and typed_id_list(row[0], nonempty=True) and typed_id(row[1])
            for row in value["minimallyJointVisible"]
        )
    )


def policy_payload_is_typed(value: Any) -> bool:
    def component(component_value: Any) -> bool:
        return (
            isinstance(component_value, dict)
            and list(component_value) == ["valueType", "lifecycle", "applicableEntries"]
            and typed_manifest_value_type(component_value["valueType"])
            and component_value["lifecycle"] in {"EntryInput", "PersistentState", "DerivedPublic"}
            and typed_id_list(component_value["applicableEntries"], nonempty=True)
        )

    def entry(entry_value: Any) -> bool:
        return (
            isinstance(entry_value, dict)
            and list(entry_value) == ["llvmSymbol", "argumentRoles", "allowedReturnClasses"]
            and isinstance(entry_value["llvmSymbol"], str)
            and isinstance(entry_value["argumentRoles"], list)
            and all(typed_argument_role(item) for item in entry_value["argumentRoles"])
            and isinstance(entry_value["allowedReturnClasses"], list)
            and bool(entry_value["allowedReturnClasses"])
            and typed_canonical_unique_list(entry_value["allowedReturnClasses"])
            and all(typed_return_class(item) for item in entry_value["allowedReturnClasses"])
        )

    return (
        typed_digest(value["policyId"])
        and typed_id_list(value["principals"], nonempty=True)
        and typed_id_list(value["hosts"], nonempty=True)
        and typed_visibility(value["hostVisibility"])
        and isinstance(value["maximalAdversaryCoalitions"], list)
        and typed_canonical_unique_list(value["maximalAdversaryCoalitions"], nonempty=True)
        and all(typed_id_list(coalition, nonempty=True) for coalition in value["maximalAdversaryCoalitions"])
        and typed_map_rows(value["components"], typed_id, component)
        and all(typed_visibility(value[field]) for field in ["componentVisibility", "outputVisibility", "errorVisibility"])
        and typed_map_rows(value["entries"], typed_id, entry) and bool(value["entries"])
        and typed_map_rows(value["publicBounds"], typed_id, typed_policy_expr)
        and isinstance(value["preconditions"], list) and all(typed_policy_expr(item) for item in value["preconditions"])
        and typed_map_rows(value["publicAliasTopologyIds"], typed_id, typed_id_list)
        and typed_map_rows(value["expectedVariableAssertions"], typed_id, lambda item:
            isinstance(item, dict) and list(item) == ["entry", "coalition", "component"]
            and typed_id(item["entry"]) and typed_id_list(item["coalition"])
            and typed_id(item["component"]))
        and typed_map_rows(value["allocaSizeBindings"], typed_id, typed_policy_expr)
        and isinstance(value["releasePolicyReviewConfig"], dict)
        and list(value["releasePolicyReviewConfig"]) == ["capacityWarningThresholdBits", "enabledLintSet", "versionAndSemantics"]
        and isinstance(value["releasePolicyReviewConfig"]["capacityWarningThresholdBits"], dict)
        and list(value["releasePolicyReviewConfig"]["capacityWarningThresholdBits"]) == ["numerator", "denominator"]
        and typed_nat(value["releasePolicyReviewConfig"]["capacityWarningThresholdBits"]["numerator"])
        and typed_pos(value["releasePolicyReviewConfig"]["capacityWarningThresholdBits"]["denominator"])
        and value["releasePolicyReviewConfig"]["enabledLintSet"] == LINT_CLASSES
        and typed_digest(value["releasePolicyReviewConfig"]["versionAndSemantics"])
        and typed_map_rows(value["entryPlacement"], typed_id, typed_id)
        and typed_map_rows(value["releaseBindings"], typed_id, typed_digest)
        # Rev4.1 has no accepted grammar for adaptive persistent invariants.
        and value["persistentInvariants"] == []
        and typed_tag(value["invocationClaim"], "SingleInvocation")
        and typed_map_rows(value["contractBindings"], typed_id, typed_id)
    )


def typed_abi_root(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["rootId", "argumentIndex", "fixedByteLength", "alignmentBytes", "permission", "entryInitialization", "host", "lifetimeOwner"]
        and typed_id(value["rootId"]) and typed_nat(value["argumentIndex"])
        and typed_nat(value["fixedByteLength"]) and typed_pos(value["alignmentBytes"])
        and value["alignmentBytes"] & (value["alignmentBytes"] - 1) == 0
        and value["permission"] in {"ReadOnly", "WriteOnly", "ReadWrite"}
        and value["entryInitialization"] in {"Initialized", "Uninitialized"}
        and typed_id(value["host"]) and value["lifetimeOwner"] in {"Caller", "Entry"}
    )


def typed_payload_reference(value: Any) -> bool:
    return any(typed_args(value, tag, [typed_id]) for tag in [
        "ContractMetadataOutputPayloadV2", "ContractFailureOutputPayloadV2",
    ])


def typed_output_source(value: Any) -> bool:
    return any([
        typed_args(value, "ReturnBitsV2", [typed_id, typed_nat, typed_pos, typed_bit_encoding]),
        typed_args(value, "RootBytesAtTerminationV2", [typed_id, typed_id, typed_nat, typed_pos, typed_bit_encoding]),
        typed_args(value, "ContractEventBytesV2", [typed_id, typed_nat, typed_payload_reference, typed_pos, typed_bit_encoding]),
    ])


def typed_output_footprint(value: Any) -> bool:
    return any([
        typed_args(value, "ReturnBitV2", [typed_id, typed_nat]),
        typed_args(value, "RootByteV2", [typed_id, typed_id, typed_nat]),
        typed_args(value, "ContractEventByteV2", [typed_id, typed_nat, typed_payload_reference, typed_nat]),
    ])


def typed_error_source(value: Any) -> bool:
    return any([
        typed_args(value, "ReturnBitsAtFailureV2", [typed_id, typed_return_class, typed_nat, typed_pos, typed_bit_encoding]),
        typed_args(value, "RootSliceAtFailureV2", [typed_id, typed_return_class, typed_root_slice]),
        typed_args(value, "ContractFailureErrorSourceV2", [typed_id, typed_id]),
        typed_tag(value, "VerifierUBRiskPayloadV2"),
    ])


def abi_payload_is_typed(value: Any) -> bool:
    def entry(entry_value: Any) -> bool:
        return (
            isinstance(entry_value, dict)
            and list(entry_value) == ["functionType", "roots", "returnObservationHost", "returnBitWidth", "declaredErrorFields"]
            and isinstance(entry_value["functionType"], str)
            and isinstance(entry_value["roots"], list) and typed_unique_list(entry_value["roots"])
            and all(typed_abi_root(item) for item in entry_value["roots"])
            and typed_id(entry_value["returnObservationHost"])
            and typed_map_rows(entry_value["returnBitWidth"], typed_return_class, typed_nat)
            and typed_id_list(entry_value["declaredErrorFields"])
        )

    def named_carrier(item: Any) -> bool:
        return typed_args(item, "ValueCarrierDeclV2", [typed_manifest_value_type, typed_carrier])

    def output_binding(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["outputId", "source", "footprint"]
            and typed_id(item["outputId"]) and typed_output_source(item["source"])
            and isinstance(item["footprint"], list) and bool(item["footprint"])
            and typed_unique_list(item["footprint"], nonempty=True)
            and all(typed_output_footprint(part) for part in item["footprint"])
        )

    def error_binding(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["errorFieldId", "payloadType", "source", "encoding"]
            and typed_id(item["errorFieldId"]) and typed_manifest_value_type(item["payloadType"])
            and typed_error_source(item["source"]) and typed_bit_encoding(item["encoding"])
        )

    def alias_topology(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["equivalenceClasses", "overlaps"]
            and isinstance(item["equivalenceClasses"], list)
            and all(typed_id_list(group, nonempty=True) for group in item["equivalenceClasses"])
            and item["overlaps"] == []
        )

    pair_ids = lambda item: isinstance(item, list) and len(item) == 2 and all(typed_id(part) for part in item)
    entry_return = lambda item: isinstance(item, list) and len(item) == 2 and typed_id(item[0]) and typed_return_class(item[1])
    boundary_ordinal = lambda item: isinstance(item, list) and len(item) == 2 and typed_id(item[0]) and typed_nat(item[1])
    return (
        typed_digest(value["abiId"]) and isinstance(value["targetDataLayout"], str)
        and typed_map_rows(value["entries"], typed_id, entry)
        and typed_map_rows(value["carriers"], pair_ids, typed_carrier)
        and typed_map_rows(value["namedCarriers"], typed_id, named_carrier)
        and typed_map_rows(value["outputBindings"], typed_id, output_binding)
        and typed_map_rows(value["returnClassBindings"], pair_ids, typed_return_class)
        and typed_map_rows(value["terminalOutputOrder"], entry_return, typed_id_list)
        and typed_map_rows(value["contractEventOutputOrder"], boundary_ordinal, typed_id_list)
        and typed_map_rows(value["errorFields"], typed_id, error_binding)
        and typed_id(value["ubRiskErrorFieldId"])
        and typed_map_rows(value["aliasTopologyBindings"], pair_ids, alias_topology)
    )


def typed_relation_field_type(value: Any) -> bool:
    return any([
        typed_tag(value, "BoolFieldV2"),
        typed_args(value, "BVFieldV2", [typed_pos]),
        typed_args(value, "NatFieldV2", [typed_nat]),
        typed_args(value, "FiniteTagFieldV2", [typed_id, lambda items: typed_id_list(items, nonempty=True)]),
    ])


def typed_relation_tuple_type(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["fields"]
        and isinstance(value["fields"], list) and bool(value["fields"])
        and typed_unique_list(value["fields"], nonempty=True)
        and all(
            isinstance(field, dict) and list(field) == ["fieldPath", "fieldType"]
            and typed_relation_field_path(field["fieldPath"])
            and typed_relation_field_type(field["fieldType"])
            for field in value["fields"]
        )
    )


def typed_relation_field_value(value: Any) -> bool:
    return any([
        typed_args(value, "BoolFieldValueV2", [lambda item: isinstance(item, bool)]),
        typed_args(value, "BVFieldValueV2", [typed_pos, lambda item: isinstance(item, str) and re.fullmatch(r"[01]+", item) is not None]),
        typed_args(value, "NatFieldValueV2", [typed_nat, typed_nat]),
        typed_args(value, "FiniteTagFieldValueV2", [typed_id, typed_id]),
    ])


def typed_relation_tuple_value(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["fields"]
        and isinstance(value["fields"], list)
        and all(typed_relation_field_value(item) for item in value["fields"])
    )


def typed_finite_pair_table(value: Any) -> bool:
    if (
        not isinstance(value, dict)
        or list(value) != ["leftValues", "rightValues", "allowedPairBitmap"]
        or not isinstance(value["leftValues"], list)
        or not isinstance(value["rightValues"], list)
        or not typed_canonical_unique_list(value["leftValues"])
        or not typed_canonical_unique_list(value["rightValues"])
        or not all(typed_relation_tuple_value(item) for item in value["leftValues"] + value["rightValues"])
        or not isinstance(value["allowedPairBitmap"], str)
        or re.fullmatch(r"[01]*", value["allowedPairBitmap"]) is None
    ):
        return False
    return len(value["allowedPairBitmap"]) == len(value["leftValues"]) * len(value["rightValues"])


def typed_canonical_relation(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["relationId", "relationRole", "leftTupleType", "rightTupleType", "representation"]
        and typed_id(value["relationId"])
        and any(typed_tag(value["relationRole"], tag) for tag in ["MechanismPairedCoupling", "TimingPairedCoupling"])
        and typed_relation_tuple_type(value["leftTupleType"])
        and typed_relation_tuple_type(value["rightTupleType"])
        and (typed_policy_expr(value["representation"]) or typed_finite_pair_table(value["representation"]))
    )


def typed_contract_value_type(value: Any) -> bool:
    return (
        typed_args(value, "ValueV2", [lambda item:
            typed_tag(item, "BoolValueV2") or typed_args(item, "BVValueV2", [typed_pos])])
        or typed_args(value, "ExistingPointerV2", [lambda item: item == 0])
    )


def typed_contract_field_decl(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["fieldId", "valueType"]
        and typed_id(value["fieldId"]) and typed_contract_value_type(value["valueType"])
    )


def typed_contract_function(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and list(value) == ["functionId", "inputTupleType", "outputTupleType", "outputExpressions"]
        and typed_id(value["functionId"])
        and typed_relation_tuple_type(value["inputTupleType"])
        and typed_relation_tuple_type(value["outputTupleType"])
        and isinstance(value["outputExpressions"], list) and bool(value["outputExpressions"])
        and typed_unique_list(value["outputExpressions"], nonempty=True)
        and all(
            isinstance(row, dict) and list(row) == ["fieldPath", "expression"]
            and typed_relation_field_path(row["fieldPath"])
            and typed_policy_expr(row["expression"])
            for row in value["outputExpressions"]
        )
    )


def typed_contract_event_slot(value: Any) -> bool:
    return any(typed_args(value, tag, [typed_id]) for tag in ["MetadataSlotV2", "FailureSlotV2"])


def contract_payload_is_typed(value: Any) -> bool:
    def signature(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["arguments", "result"]
            and isinstance(item["arguments"], list)
            and typed_unique_list(item["arguments"])
            and all(typed_contract_field_decl(field) for field in item["arguments"])
            and typed_option(item["result"], typed_contract_field_decl)
        )

    def occurrence(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["boundaryId", "site", "choiceType", "eventOrder"]
            and typed_id(item["boundaryId"]) and typed_id(item["site"])
            and typed_tag(item["choiceType"], "Unit")
            and isinstance(item["eventOrder"], list)
            and typed_unique_list(item["eventOrder"])
            and all(typed_contract_event_slot(slot) for slot in item["eventOrder"])
        )

    def object_slice(item: Any) -> bool:
        return (
            typed_args(item, "PointerArgumentSliceV2", [typed_nat, typed_nat, typed_pos])
            or typed_args(item, "GlobalSliceV2", [typed_id, typed_nat, typed_pos])
        )

    def memory_effect(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["effectId", "kind", "target"]
            and typed_id(item["effectId"]) and item["kind"] in {"Read", "Write", "Initialize"}
            and object_slice(item["target"])
        )

    def failure(item: Any) -> bool:
        return (
            isinstance(item, dict)
            and list(item) == ["failureId", "errorFieldId", "payloadType", "eventOrdinal", "location"]
            and typed_id(item["failureId"]) and typed_id(item["errorFieldId"])
            and typed_manifest_value_type(item["payloadType"])
            and typed_nat(item["eventOrdinal"])
            and item["location"] in {"BoundarySource", "BoundaryDestinations"}
        )

    def metadata(item: Any) -> bool:
        return (
            isinstance(item, dict)
            and list(item) == ["metadataFieldId", "valueType", "eventOrdinal", "location"]
            and typed_id(item["metadataFieldId"])
            and typed_manifest_value_type(item["valueType"])
            and typed_nat(item["eventOrdinal"])
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
            and typed_id(item["contractId"])
            and isinstance(item["supportedCoalitionMaxima"], list)
            and typed_canonical_unique_list(item["supportedCoalitionMaxima"], nonempty=True)
            and all(typed_id_list(coalition) for coalition in item["supportedCoalitionMaxima"])
            and signature(item["signature"])
            and typed_tag(item["stateType"], "None")
            and item["choiceDomain"] == [OrderedDict([("tag", "Unit")])]
            and typed_map_rows(item["occurrences"], typed_id, occurrence)
            and typed_contract_function(item["function"])
            and typed_map_rows(item["pairedChoiceCoupling"], typed_digest, typed_canonical_relation)
            and isinstance(item["memoryEffects"], list) and all(memory_effect(effect) for effect in item["memoryEffects"])
            and typed_unique_list(item["memoryEffects"])
            and isinstance(item["failures"], list) and typed_unique_list(item["failures"])
            and all(failure(row) for row in item["failures"])
            and typed_map_rows(item["contractVisibleMetadata"], typed_id, metadata)
            and typed_visibility(item["contractMetadataVisibility"])
            and typed_tag(item["stateRelation"], "None")
            and typed_tag(item["releaseBehavior"], "NoContractReleaseV2")
            and typed_tag(item["freshAllocationBehavior"], "NoFreshContractAllocationV2")
            and typed_digest(item["versionAndImplementationBoundary"])
        )

    return (
        value["formatId"] == "SPS-ContractTable-v2"
        and isinstance(value["contracts"], list)
        and all(contract(item) for item in value["contracts"])
        and [item["contractId"] for item in value["contracts"]]
        == sorted(item["contractId"] for item in value["contracts"])
        and len({item["contractId"] for item in value["contracts"]}) == len(value["contracts"])
    )


def typed_release_type(value: Any) -> bool:
    if typed_args(value, "BVType", [typed_pos, lambda item: item in {"LittleEndian", "BigEndian"}]):
        return True
    return typed_args(value, "TupleType", [
        lambda fields: isinstance(fields, list) and bool(fields)
        and all(
            isinstance(field, list) and len(field) == 2 and typed_id(field[0])
            and typed_release_type(field[1])
            for field in fields
        )
        and len({field[0] for field in fields}) == len(fields)
    ])


def typed_release_spec(value: Any) -> bool:
    if not isinstance(value, dict) or list(value) != RELEASE_SPEC_V2_FIELDS:
        return False
    implementation = value["implementation"]
    audience = value["audience"]
    return (
        typed_id(value["releaseId"]) and typed_id(value["site"])
        and isinstance(implementation, dict)
        and list(implementation) == ["wrapperFunction", "emitMarkerInstructionId"]
        and typed_id(implementation["wrapperFunction"])
        and typed_id(implementation["emitMarkerInstructionId"])
        and typed_release_type(value["type"])
        and typed_policy_expr(value["expression"])
        and typed_policy_expr(value["occurrenceGuard"])
        and isinstance(audience, dict)
        and list(audience) == ["worldVisible", "memberVisible", "minimallyJointVisible"]
        and isinstance(audience["worldVisible"], bool)
        and typed_id_list(audience["memberVisible"])
        and isinstance(audience["minimallyJointVisible"], list)
        and typed_canonical_unique_list(audience["minimallyJointVisible"])
        and all(typed_id_list(coalition, nonempty=True) for coalition in audience["minimallyJointVisible"])
        and isinstance(value["footprint"], list) and bool(value["footprint"])
        and typed_canonical_unique_list(value["footprint"], nonempty=True)
        and all(typed_args(item, "ReleasePayloadByteV2", [typed_nat]) for item in value["footprint"])
        and typed_policy_expr(value["multiplicity"])
        and typed_map_rows(value["activationClaims"], typed_id, lambda item:
            typed_tag(item, "RequiredReachable") or typed_tag(item, "NotApplicable")
            or (isinstance(item, dict) and list(item) == ["tag", "reasonCode"]
                and item["tag"] == "Dormant" and typed_id(item["reasonCode"])))
        and value["deterministicSemantics"] == policy_semantics_version()
    )


def typed_option_row(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["name", "value"]
        and isinstance(value["name"], str)
        and (
            isinstance(value["value"], (bool, str))
            or typed_nat(value["value"])
        )
    )


def typed_alias_topology(value: Any) -> bool:
    return (
        isinstance(value, dict) and list(value) == ["equivalenceClasses", "overlaps"]
        and isinstance(value["equivalenceClasses"], list)
        and typed_canonical_unique_list(value["equivalenceClasses"])
        and all(typed_id_list(group, nonempty=True) for group in value["equivalenceClasses"])
        and value["overlaps"] == []
    )


def typed_manifest_value(value: Any) -> bool:
    if typed_args(value, "BoolLiteralValueV2", [lambda item: isinstance(item, bool)]):
        return True
    if typed_args(value, "BVLiteralValueV2", [
        typed_pos,
        lambda item: isinstance(item, str) and re.fullmatch(r"[01]+", item) is not None,
    ]):
        return len(value["args"][1]) == value["args"][0]
    if typed_args(value, "FixedBytesLiteralValueV2", [
        typed_pos,
        lambda item: isinstance(item, str) and re.fullmatch(r"(?:[0-9a-f]{2})+", item) is not None,
    ]):
        return len(value["args"][1]) == 2 * value["args"][0]
    return typed_args(value, "TupleLiteralValueV2", [
        lambda items: isinstance(items, list) and bool(items)
        and all(typed_manifest_value(item) for item in items)
    ])


def typed_public_configuration_source(value: Any) -> bool:
    return any([
        typed_args(value, "ComponentConfigV2", [typed_id]),
        typed_args(value, "BoundConfigV2", [typed_id]),
        typed_args(value, "ReleaseOccurrenceCounterConfigV2", [typed_id, typed_nat_sort]),
        typed_args(value, "TimingOccurrenceCounterConfigV2", [typed_id, typed_nat_sort]),
    ])


def typed_public_configuration_value(value: Any) -> bool:
    return (
        typed_args(value, "ComponentConfigValueV2", [typed_manifest_value])
        or typed_args(value, "NaturalConfigValueV2", [typed_nat_sort, typed_nat])
    )


def llvm_build_payload_is_typed(value: Any) -> bool:
    return (
        isinstance(value["repository"], str) and isinstance(value["tag"], str)
        and isinstance(value["commit"], str) and re.fullmatch(r"[0-9a-f]{40}", value["commit"]) is not None
        and typed_digest(value["compilerBinaryDigest"])
        and isinstance(value["libraryDigests"], list)
        and typed_canonical_unique_list(value["libraryDigests"])
        and all(
            isinstance(row, dict) and list(row) == ["name", "digest"]
            and isinstance(row["name"], str) and typed_digest(row["digest"])
            for row in value["libraryDigests"]
        )
        and len({row["name"] for row in value["libraryDigests"]}) == len(value["libraryDigests"])
    )


def sps_build_payload_is_typed(value: Any) -> bool:
    return (
        isinstance(value["patchCommit"], str) and re.fullmatch(r"[0-9a-f]{40}", value["patchCommit"]) is not None
        and all(typed_digest(value[field]) for field in [
            "verifierCoreBinaryDigest", "normalizerBinaryDigest", "auditorBinaryDigest",
            "transitionRuleTableDigest",
        ])
        and typed_id(value["normalizerId"]) and typed_id(value["auditorId"])
        and isinstance(value["normalizerOptions"], list)
        and all(typed_option_row(row) for row in value["normalizerOptions"])
    )


def pass_trace_payload_is_typed(value: Any) -> bool:
    freeze = value["freezeCoordinate"]
    return (
        isinstance(value["rows"], list) and bool(value["rows"])
        and all(
            isinstance(row, dict)
            and list(row) == ["ordinal", "passId", "implementationDigest", "pluginDigest", "options", "mutatesIR"]
            and typed_nat(row["ordinal"]) and typed_id(row["passId"])
            and typed_digest(row["implementationDigest"])
            and typed_option(row["pluginDigest"], typed_digest)
            and isinstance(row["options"], list) and all(typed_option_row(item) for item in row["options"])
            and isinstance(row["mutatesIR"], bool)
            for row in value["rows"]
        )
        and [row["ordinal"] for row in value["rows"]] == list(range(len(value["rows"])))
        and isinstance(freeze, dict)
        and list(freeze) == ["llvmCommit", "targetPassConfigConcreteClass", "instructionSelector"]
        and isinstance(freeze["llvmCommit"], str) and re.fullmatch(r"[0-9a-f]{40}", freeze["llvmCommit"]) is not None
        and all(isinstance(freeze[field], str) for field in ["targetPassConfigConcreteClass", "instructionSelector"])
    )


def target_configuration_payload_is_typed(value: Any) -> bool:
    string_fields = [
        "targetTriple", "dataLayout", "targetCPU", "tuneCPU", "relocationModel",
        "codeModel", "codegenOptimizationLevel", "floatABI", "instructionSelector",
        "ltoMode", "sanitizerMode",
    ]
    return (
        all(isinstance(value[field], str) for field in string_fields)
        and isinstance(value["targetFeatures"], list)
        and typed_canonical_unique_list(value["targetFeatures"])
        and all(isinstance(item, str) for item in value["targetFeatures"])
        and all(isinstance(value[field], bool) for field in [
            "fastISelEnabled", "globalISelEnabled", "globalISelFallbackEnabled",
        ])
        and isinstance(value["canonicalBitcodeWriterOptions"], list)
        and all(typed_option_row(row) for row in value["canonicalBitcodeWriterOptions"])
    )


def placement_payload_is_typed(value: Any) -> bool:
    def location(item: Any) -> bool:
        return (
            isinstance(item, dict) and list(item) == ["source", "destinations"]
            and typed_id(item["source"]) and typed_id_list(item["destinations"])
        )

    return (
        value["formatId"] == "SPS-FunctionPlacement-v2"
        and all(typed_map_rows(value[field], typed_id, typed_id) for field in [
            "functionHost", "instructionHost", "globalHost",
        ])
        and typed_map_rows(value["boundaryLocations"], typed_id, location)
    )


def alias_topology_payload_is_typed(value: Any) -> bool:
    pair_ids = lambda item: isinstance(item, list) and len(item) == 2 and all(typed_id(part) for part in item)
    return (
        value["formatId"] == "SPS-Alias-Topology-Digest-Preimage-v2"
        and typed_id_list(value["selectedTopologyIds"])
        and typed_map_rows(value["bindings"], pair_ids, typed_alias_topology)
    )


def stable_ir_payload_is_typed(value: Any) -> bool:
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
        typed_args(item, "InstructionSyntheticSiteLocatorV2", [typed_id, lambda role: role in synthetic_roles, typed_nat])
        or typed_args(item, "LoopSyntheticSiteLocatorV2", [typed_id, lambda role: role == "BoundRemainder", lambda ordinal: ordinal == 0])
    )
    validators = {
        "functions": lambda item: exact_record(item, ["functionSymbol"], [lambda field: isinstance(field, str)]),
        "blocks": lambda item: exact_record(item, ["functionId", "blockOrdinal"], [typed_id, typed_nat]),
        "arguments": lambda item: exact_record(item, ["functionId", "argumentOrdinal"], [typed_id, typed_nat]),
        "instructions": lambda item: exact_record(item, ["functionId", "blockOrdinal", "instructionOrdinal"], [typed_id, typed_nat, typed_nat]),
        "predecessorEdges": lambda item: exact_record(item, ["functionId", "predecessorBlockOrdinal", "successorBlockOrdinal", "successorOperandOrdinal"], [typed_id, typed_nat, typed_nat, typed_nat]),
        "loops": lambda item: exact_record(item, ["functionId", "headerBlockOrdinal", "orderedBackedgeIds"], [typed_id, typed_nat, typed_id_list]),
        "instructionSites": lambda item: exact_record(item, ["ownerInstructionId", "siteRole", "roleOrdinal"], [typed_id, lambda role: role == "OrdinaryTransition", lambda ordinal: ordinal == 0]),
        "syntheticSites": synthetic,
    }
    if not all(
        isinstance(value[field], list) and all(predicate(item) for item in value[field])
        for field, predicate in validators.items()
    ) or not all(typed_unique_list(value[field]) for field in validators):
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


def timing_environment_payload_is_typed(value: Any) -> bool:
    def occurrence(item: Any) -> bool:
        return (
            isinstance(item, dict)
            and list(item) == ["timingOccurrenceId", "site", "occurrenceGuard", "multiplicity", "configurationSources", "allowedChoiceIds"]
            and typed_id(item["timingOccurrenceId"]) and typed_id(item["site"])
            and typed_policy_expr(item["occurrenceGuard"])
            and typed_policy_expr(item["multiplicity"])
            and isinstance(item["configurationSources"], list)
            and typed_canonical_unique_list(item["configurationSources"])
            and all(typed_public_configuration_source(source) for source in item["configurationSources"])
            and typed_id_list(item["allowedChoiceIds"], nonempty=True)
        )

    def latency_row(item: Any) -> bool:
        return (
            isinstance(item, dict)
            and list(item) == ["timingOccurrenceId", "publicConfigurationValues", "choiceId", "latencyClassId"]
            and typed_id(item["timingOccurrenceId"])
            and isinstance(item["publicConfigurationValues"], list)
            and all(typed_public_configuration_value(part) for part in item["publicConfigurationValues"])
            and typed_id(item["choiceId"]) and typed_id(item["latencyClassId"])
        )

    return (
        typed_digest(value["timingEnvironmentId"])
        and isinstance(value["choiceDomain"], list)
        and typed_canonical_unique_list(value["choiceDomain"])
        and all(isinstance(row, dict) and list(row) == ["choiceId"] and typed_id(row["choiceId"]) for row in value["choiceDomain"])
        and typed_map_rows(value["occurrences"], typed_id, occurrence)
        and isinstance(value["latencyMeaning"], list)
        and typed_canonical_unique_list(value["latencyMeaning"])
        and all(latency_row(row) for row in value["latencyMeaning"])
        and isinstance(value["latencyClasses"], list) and bool(value["latencyClasses"])
        and typed_canonical_unique_list(value["latencyClasses"], nonempty=True)
        and all(isinstance(row, dict) and list(row) == ["latencyClassId"] and typed_id(row["latencyClassId"]) for row in value["latencyClasses"])
        and typed_map_rows(value["pairedChoiceCoupling"], typed_digest, typed_canonical_relation)
        and typed_digest(value["versionAndObservationBoundary"])
    )


def latency_class_payload_is_typed(value: Any) -> bool:
    return (
        isinstance(value["siteSchemas"], list)
        and typed_canonical_unique_list(value["siteSchemas"])
        and all(
            isinstance(row, dict) and list(row) == ["siteId", "configurationSources", "timingOccurrenceId"]
            and typed_id(row["siteId"]) and isinstance(row["configurationSources"], list)
            and typed_canonical_unique_list(row["configurationSources"])
            and all(typed_public_configuration_source(item) for item in row["configurationSources"])
            and typed_option(row["timingOccurrenceId"], typed_id)
            for row in value["siteSchemas"]
        )
        and isinstance(value["rows"], list)
        and typed_canonical_unique_list(value["rows"])
        and all(
            isinstance(row, dict) and list(row) == ["siteId", "publicConfigurationValues", "timingChoiceId", "latencyClassId"]
            and typed_id(row["siteId"]) and isinstance(row["publicConfigurationValues"], list)
            and all(typed_public_configuration_value(item) for item in row["publicConfigurationValues"])
            and typed_option(row["timingChoiceId"], typed_id) and typed_id(row["latencyClassId"])
            for row in value["rows"]
        )
    )


def entry_scope_payload_is_typed(value: Any) -> bool:
    return (
        isinstance(value["rows"], list) and bool(value["rows"])
        and all(
            isinstance(row, dict)
            and list(row) == ["entryId", "entryFunctionId", "reachableFunctionIds", "reachableBoundaryIds", "reachableReleaseIds"]
            and typed_id(row["entryId"]) and typed_id(row["entryFunctionId"])
            and all(typed_id_list(row[field]) for field in ["reachableFunctionIds", "reachableBoundaryIds", "reachableReleaseIds"])
            for row in value["rows"]
        )
        and [row["entryId"] for row in value["rows"]] == sorted(row["entryId"] for row in value["rows"])
        and len({row["entryId"] for row in value["rows"]}) == len(value["rows"])
    )


def profile_configuration_payload_is_typed(value: Any) -> bool:
    return (
        all(typed_digest(value[field]) for field in [
            "globalRegionTableDigest", "preflightTaskScheduleDigest", "publicAliasTopologyDigest",
        ])
        and isinstance(value["integerWidths"], list) and bool(value["integerWidths"])
        and all(typed_pos(item) for item in value["integerWidths"])
        and value["integerWidths"] == sorted(value["integerWidths"])
        and len(set(value["integerWidths"])) == len(value["integerWidths"])
        and isinstance(value["floatTypes"], list) and all(isinstance(item, str) for item in value["floatTypes"])
        and typed_pos(value["maxVectorLanesBeforeNormalization"])
        and isinstance(value["loopBoundBindings"], list)
        and typed_canonical_unique_list(value["loopBoundBindings"])
        and all(
            isinstance(row, dict) and list(row) == ["loopId", "boundId", "engineCap"]
            and typed_id(row["loopId"]) and typed_id(row["boundId"]) and typed_nat(row["engineCap"])
            for row in value["loopBoundBindings"]
        )
        and isinstance(value["allocaSizeBindings"], list)
        and typed_canonical_unique_list(value["allocaSizeBindings"])
        and all(
            isinstance(row, dict) and list(row) == ["allocaSiteId", "expressionSiteId"]
            and typed_id(row["allocaSiteId"]) and typed_id(row["expressionSiteId"])
            for row in value["allocaSizeBindings"]
        )
        and typed_pos(value["enginePathCap"]) and typed_pos(value["engineByteCap"])
        and all(isinstance(value[field], str) for field in [
            "moduleFlagPolicy", "codegenAttributePolicy", "stackProtectorPolicy",
        ])
    )


def global_region_payload_is_typed(value: Any) -> bool:
    def row_is_typed(row: Any) -> bool:
        expected = [
            "globalId", "llvmSymbol", "llvmStorageType", "linkage", "mutability",
            "storageEncoding", "sizeBytes", "alignmentBytes", "addressSpace",
            "initializerBytes", "host", "applicableEntries",
        ]
        return (
            isinstance(row, dict) and list(row) == expected
            and typed_id(row["globalId"]) and isinstance(row["llvmSymbol"], str)
            and isinstance(row["llvmStorageType"], str) and row["linkage"] in {"Internal", "Private"}
            and row["mutability"] == "ImmutableV2"
            and row["storageEncoding"] == "PointerFreePaddingFreeExactBytesV2"
            and typed_nat(row["sizeBytes"]) and typed_pos(row["alignmentBytes"])
            and row["alignmentBytes"] & (row["alignmentBytes"] - 1) == 0
            and row["addressSpace"] == 0 and isinstance(row["initializerBytes"], str)
            and re.fullmatch(r"[0-9a-f]*", row["initializerBytes"]) is not None
            and len(row["initializerBytes"]) == 2 * row["sizeBytes"]
            and typed_id(row["host"]) and typed_id_list(row["applicableEntries"], nonempty=True)
        )

    return (
        isinstance(value["rows"], list) and all(row_is_typed(row) for row in value["rows"])
        and [row["globalId"] for row in value["rows"]] == sorted(row["globalId"] for row in value["rows"])
        and len({row["globalId"] for row in value["rows"]}) == len(value["rows"])
    )


def preflight_schedule_payload_is_typed(value: Any) -> bool:
    return (
        value["formatId"] == "SPS-Preflight-Task-Schedule-v2"
        and isinstance(value["tasks"], list)
        and all(
            isinstance(row, dict)
            and list(row) == ["taskId", "entryScope", "scannerId", "scannerImplementationDigest", "taskClass"]
            and typed_id(row["taskId"]) and typed_option(row["entryScope"], typed_id)
            and typed_id(row["scannerId"]) and typed_digest(row["scannerImplementationDigest"])
            and typed_id(row["taskClass"])
            for row in value["tasks"]
        )
        and [row["taskId"] for row in value["tasks"]] == sorted(row["taskId"] for row in value["tasks"])
        and len({row["taskId"] for row in value["tasks"]}) == len(value["tasks"])
    )


def payload_shape_matches(value: Any, template: Any, field_name: str | None = None) -> bool:
    if isinstance(template, dict):
        if not isinstance(value, dict) or list(value) != list(template):
            return False
        for key in template:
            if not payload_shape_matches(value[key], template[key], key):
                return False
        return True
    if isinstance(template, list):
        if not isinstance(value, list):
            return False
        if not template:
            return True
        if len(template) == 1:
            return all(payload_shape_matches(item, template[0]) for item in value)
        return len(value) == len(template) and all(
            payload_shape_matches(item, expected)
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


def canonical_payload_collections_are_typed(field_name: str, value: Any) -> bool:
    if field_name == "llvmBuild":
        return llvm_build_payload_is_typed(value)
    if field_name == "spsBuild":
        return sps_build_payload_is_typed(value)
    if field_name == "passTrace":
        return pass_trace_payload_is_typed(value)
    if field_name == "targetConfiguration":
        return target_configuration_payload_is_typed(value)
    if field_name == "policy":
        return policy_payload_is_typed(value)
    if field_name == "abi":
        return abi_payload_is_typed(value)
    if field_name == "contractTable":
        return contract_payload_is_typed(value)
    if field_name == "placementTable":
        return placement_payload_is_typed(value)
    if field_name == "aliasTopology":
        return alias_topology_payload_is_typed(value)
    if field_name == "allocaSizeBindings":
        return (
            value["formatId"] == "SPS-Alloca-Size-Bindings-Digest-Preimage-v2"
            and typed_map_rows(value["bindings"], typed_id, typed_policy_expr)
        )
    if field_name == "publicBounds":
        return (
            value["formatId"] == "SPS-Public-Bounds-Digest-Preimage-v2"
            and typed_map_rows(value["bounds"], typed_id, typed_policy_expr)
        )
    if field_name == "preconditions":
        return (
            value["formatId"] == "SPS-Preconditions-Digest-Preimage-v2"
            and isinstance(value["predicates"], list)
            and typed_canonical_unique_list(value["predicates"])
            and all(typed_policy_expr(item) for item in value["predicates"])
        )
    if field_name == "stableIRBindings":
        return stable_ir_payload_is_typed(value)
    if field_name == "latencyClassTable":
        return latency_class_payload_is_typed(value)
    if field_name == "timingEnvironment":
        return timing_environment_payload_is_typed(value)
    if field_name == "entryScope":
        return entry_scope_payload_is_typed(value)
    if field_name == "profileConfiguration":
        return profile_configuration_payload_is_typed(value)
    if field_name == "globalRegionTable":
        return global_region_payload_is_typed(value)
    if field_name == "preflightTaskSchedule":
        return preflight_schedule_payload_is_typed(value)
    if field_name == "stackProtectorPreflight":
        return all(typed_id_list(rows) for rows in value.values())
    if field_name == "policyReviewConfiguration":
        threshold = value["capacityWarningThresholdBits"]
        return (
            isinstance(threshold, dict) and list(threshold) == ["numerator", "denominator"]
            and typed_nat(threshold["numerator"]) and typed_pos(threshold["denominator"])
            and value["enabledLintSet"] == LINT_CLASSES
            and typed_digest(value["versionAndSemantics"])
        )
    return True


def canonical_payload_is_bounded(field_name: str, value: Any) -> bool:
    if field_name == "releaseTable":
        try:
            release_table_entries(value)
        except (KeyError, TypeError, ValueError):
            return False
        return True
    if field_name == "interfaceManifest":
        return value == conformance_interface_manifest()
    try:
        template = canonical_payload(field_name)
    except KeyError:
        return False
    if not payload_shape_matches(value, template):
        return False
    if not canonical_payload_collections_are_typed(field_name, value):
        return False
    if field_name in EXACT_CANONICAL_PAYLOADS and value != template:
        return False
    if "formatId" in template and value["formatId"] != template["formatId"]:
        return False
    if field_name == "llvmBuild":
        return value["tag"] == template["tag"] and value["commit"] == template["commit"]
    if field_name == "spsBuild":
        return (
            re.fullmatch(r"[0-9a-f]{40}", value["patchCommit"]) is not None
            and value["transitionRuleTableDigest"] == canonical_input("transitionRuleTable")["sha256"]
        )
    if field_name == "targetConfiguration":
        return all(value[key] == template[key] for key in [
            "ltoMode", "sanitizerMode", "instructionSelector",
            "fastISelEnabled", "globalISelEnabled", "globalISelFallbackEnabled",
        ])
    if field_name == "profileConfiguration":
        return all(value[key] == template[key] for key in [
            "floatTypes", "moduleFlagPolicy", "codegenAttributePolicy",
            "stackProtectorPolicy", "globalRegionTableDigest",
            "preflightTaskScheduleDigest", "publicAliasTopologyDigest",
        ])
    if field_name == "policyReviewConfiguration":
        return value["enabledLintSet"] == LINT_CLASSES
    if field_name == "preflightTaskSchedule":
        return value["formatId"] == "SPS-Preflight-Task-Schedule-v2"
    return True


RELEASE_SPEC_V2_FIELDS = [
    "releaseId", "site", "implementation", "type", "expression",
    "occurrenceGuard", "audience", "footprint", "multiplicity",
    "activationClaims", "deterministicSemantics",
]


def release_type_widths(value: Any) -> list[int]:
    if not isinstance(value, dict) or list(value) != ["tag", "args"]:
        raise ValueError("release type must be a tag/args constructor")
    args_value = value["args"]
    if value["tag"] == "BVType":
        if (
            not isinstance(args_value, list) or len(args_value) != 2
            or isinstance(args_value[0], bool) or not isinstance(args_value[0], int)
            or args_value[0] < 1 or args_value[1] not in {"LittleEndian", "BigEndian"}
        ):
            raise ValueError("malformed BVType")
        return [args_value[0]]
    if value["tag"] == "TupleType":
        if not isinstance(args_value, list) or len(args_value) != 1:
            raise ValueError("malformed TupleType")
        field_rows = args_value[0]
        if not isinstance(field_rows, list) or not field_rows:
            raise ValueError("TupleType is empty")
        field_ids: list[str] = []
        widths: list[int] = []
        for row in field_rows:
            if not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str):
                raise ValueError("malformed TupleType field")
            if not ID_RE.fullmatch(row[0]):
                raise ValueError("invalid TupleType field ID")
            field_ids.append(row[0])
            widths.extend(release_type_widths(row[1]))
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("duplicate TupleType field ID")
        return widths
    raise ValueError("unknown release type constructor")


def release_table_entries(value: Any) -> list[tuple[Any, list[int]]]:
    if (
        not isinstance(value, dict)
        or list(value) != ["formatId", "expressionSemantics", "entries"]
        or value["formatId"] != "SPS-ReleaseTable-v2"
        or value["expressionSemantics"] != policy_semantics_version()
        or not isinstance(value["entries"], list)
    ):
        raise ValueError("malformed SPS-ReleaseTable-v2 envelope")
    result: list[tuple[Any, list[int]]] = []
    release_ids: list[str] = []
    for entry in value["entries"]:
        if not typed_release_spec(entry):
            raise ValueError("malformed typed ReleaseSpecV2")
        release_id = entry["releaseId"]
        release_ids.append(release_id)
        result.append((entry, release_type_widths(entry["type"])))
    if release_ids != sorted(release_ids) or len(release_ids) != len(set(release_ids)):
        raise ValueError("release table IDs are unsorted or duplicated")
    return result


def release_binding_failures(
    bindings: Any, machine_map: Any | None = None,
    release_table_value: Any | None = None,
) -> list[str]:
    failures: list[str] = []
    rows = bindings["rows"]
    keys = {
        "release": [row["releaseId"] for row in rows],
        "site": [row["siteId"] for row in rows],
        "wrapper": [row["implementation"]["wrapperFunction"] for row in rows],
        "instruction": [row["implementation"]["emitMarkerInstructionId"] for row in rows],
    }
    if any(len(values) != len(set(values)) for values in keys.values()):
        append_failure(failures, "XF-INTRINSIC-001")
    if any(not row["flattenedIntegerWidths"] for row in rows):
        append_failure(failures, "XF-INTRINSIC-001")
    if release_table_value is not None:
        entries = release_table_entries(release_table_value)
        if len(entries) != len(rows):
            append_failure(failures, "XF-INTRINSIC-001")
        else:
            for binding, (entry, widths) in zip(rows, entries):
                if (
                    binding["releaseId"] != entry["releaseId"]
                    or binding["siteId"] != entry["site"]
                    or binding["implementation"] != entry["implementation"]
                    or binding["flattenedIntegerWidths"] != widths
                    or binding["releaseSpecV2Digest"] != exact_digest(entry)
                ):
                    append_failure(failures, "XF-INTRINSIC-001")
    if machine_map is not None:
        map_rows = machine_map["rows"]
        map_keys = {
            "instruction": [row["emitMarkerInstructionId"] for row in map_rows],
            "pseudo": [row["mirPseudoId"] for row in map_rows],
            "boundary": [row["p4BoundaryId"] for row in map_rows],
        }
        if any(len(values) != len(set(values)) for values in map_keys.values()):
            append_failure(failures, "XF-INTRINSIC-001")
        if set(keys["instruction"]) != set(map_keys["instruction"]):
            append_failure(failures, "XF-INTRINSIC-001")
    return failures


def query_scope_is_exact(query: Any) -> bool:
    kind = query["queryKind"]["tag"]
    coalition_kinds = {
        "AuditAll", "HighVariation", "CouplingTotality", "CouplingFiberTotal",
        "CouplingSymmetry", "CouplingSchedulePreservation",
    }
    release_kinds = {"ReleaseConformance", "ReleaseActivation"}
    component_kinds = {"HighVariation"}
    relation_kinds = {
        "CouplingTotality", "CouplingFiberTotal", "CouplingSymmetry",
        "CouplingSchedulePreservation",
    }
    return (
        query["entryScope"]["tag"] == "Some"
        and (query["coalitionScope"]["tag"] == "ConcreteCoalition")
        == (kind in coalition_kinds)
        and (query["releaseScope"]["tag"] == "Some") == (kind in release_kinds)
        and (query["componentScope"]["tag"] == "Some") == (kind in component_kinds)
        and (query["relationScope"]["tag"] == "Some") == (kind in relation_kinds)
    )


def query_schedule_is_complete(queries: Any) -> bool:
    if not isinstance(queries, list) or not queries:
        return False
    kinds = [query["queryKind"]["tag"] for query in queries]
    if any(kind not in QUERY_KINDS for kind in kinds) or not all(
        query_scope_is_exact(query) for query in queries
    ):
        return False
    expected = sorted(
        queries,
        key=lambda query: (
            SCHEDULE_KIND_ORDER.index(query["queryKind"]["tag"]),
            canonical_bytes(query),
        ),
    )
    return queries == expected and len({canonical_bytes(query) for query in queries}) == len(queries)


def proof_configuration_failures(value: Any) -> list[str]:
    failures: list[str] = []
    if value["aggregationSemanticsDigest"] != exact_digest(aggregation_semantics()):
        append_failure(failures, "XF-IDENTITY-001")
    if value["replayAcceptanceSemanticsDigest"] != exact_digest(replay_acceptance_semantics()):
        append_failure(failures, "XF-IDENTITY-001")
    if not query_schedule_is_complete(value["requiredQuerySchedule"]["queries"]):
        append_failure(failures, "XF-IDENTITY-001")
    return failures


def identity_evidence_failures(value: Any) -> list[str]:
    failures: list[str] = []
    identity = value["artifactIdentity"]
    release_table_value: Any | None = None
    decoded_inputs: dict[str, Any] = {}
    if value["artifactIdentityDigest"] != exact_digest(identity):
        append_failure(failures, "XF-IDENTITY-001")
    bitcode = value["canonicalBitcode"]
    try:
        bitcode_raw = bytes.fromhex(bitcode["exactBytes"])
    except ValueError:
        bitcode_raw = b""
        append_failure(failures, "XF-IDENTITY-001")
    if bitcode["sha256"] != sha256(bitcode_raw) or identity["canonicalBitcodeHash"] != bitcode["sha256"]:
        append_failure(failures, "XF-IDENTITY-001")

    all_input_names = [*UNCHANGED_IDENTITY_INPUTS, *AUXILIARY_CONFORMANCE_INPUTS]
    for field_name in all_input_names:
        envelope = value[field_name]
        if not envelope_is_exact(envelope):
            append_failure(failures, "XF-IDENTITY-001")
        if field_name in UNCHANGED_IDENTITY_INPUTS:
            identity_field = UNCHANGED_IDENTITY_INPUTS[field_name][2]
            if identity[identity_field] != envelope["sha256"]:
                append_failure(failures, "XF-IDENTITY-001")
        try:
            decoded = require_canonical(bytes.fromhex(envelope["canonicalBytes"]))
        except (KeyError, TypeError, ValueError):
            decoded = None
        if not canonical_payload_is_bounded(field_name, decoded):
            append_failure(failures, "XF-PAYLOAD-001")
        else:
            decoded_inputs[field_name] = decoded
            if field_name == "releaseTable":
                release_table_value = decoded
            elif field_name == "interfaceManifest":
                try:
                    validate_record(decoded, "SPSConformanceInterfaceManifestV2")
                except (ValueError, TypeError):
                    append_failure(failures, "XF-PAYLOAD-001")

    proof = value["proofConfiguration"]
    if identity["proofConfigurationDigest"] != exact_digest(proof):
        append_failure(failures, "XF-IDENTITY-001")
    for rule in proof_configuration_failures(proof):
        append_failure(failures, rule)

    exact_objects = [
        ("queryScheduleDerivation", "queryScheduleDerivationDigest"),
        ("releaseMarkerBindings", "releaseMarkerBindingsDigest"),
        ("releaseMarkerMachineMap", "releaseMarkerMachineMapDigest"),
        ("intrinsicDefinition", "intrinsicDefinitionDigest"),
        ("aggregationSemantics", "aggregationSemanticsDigest"),
        ("replayAcceptanceSemantics", "replayAcceptanceSemanticsDigest"),
    ]
    for evidence_field, identity_field in exact_objects:
        if identity[identity_field] != exact_digest(value[evidence_field]):
            append_failure(failures, "XF-IDENTITY-001")

    if proof["aggregationSemanticsDigest"] != identity["aggregationSemanticsDigest"]:
        append_failure(failures, "XF-IDENTITY-001")
    if proof["replayAcceptanceSemanticsDigest"] != identity["replayAcceptanceSemanticsDigest"]:
        append_failure(failures, "XF-IDENTITY-001")
    derivation = value["queryScheduleDerivation"]
    if (
        derivation["policyDigest"] != identity["policyDigest"]
        or derivation["abiDigest"] != identity["abiDigest"]
        or derivation["releaseDigest"] != identity["releaseDigest"]
        or derivation["contractDigest"] != identity["contractDigest"]
        or derivation["entryScopeDigest"] != identity["entryScopeDigest"]
        or derivation["timingEnvironmentContractDigest"]
        != identity["timingEnvironmentContractDigest"]
        or derivation["profileConfigurationDigest"] != identity["profileConfigurationDigest"]
        or derivation["requiredQuerySchedule"] != proof["requiredQuerySchedule"]
    ):
        append_failure(failures, "XF-IDENTITY-001")
    schedule_input_names = [
        "policy", "abi", "releaseTable", "contractTable", "entryScope",
        "timingEnvironment",
    ]
    if all(name in decoded_inputs for name in schedule_input_names):
        schedule_inputs = OrderedDict((name, value[name]) for name in schedule_input_names)
        try:
            recomputed_schedule = required_query_schedule(schedule_inputs)
        except (KeyError, TypeError, ValueError):
            append_failure(failures, "XF-PAYLOAD-001")
        else:
            if (
                proof["requiredQuerySchedule"] != recomputed_schedule
                or derivation["requiredQuerySchedule"] != recomputed_schedule
            ):
                append_failure(failures, "XF-IDENTITY-001")
    required_payloads = {
        "policy", "abi", "releaseTable", "aliasTopology", "allocaSizeBindings",
        "transitionRuleTable", "policyReviewConfiguration", "profileConfiguration",
        "publicBounds", "preconditions", "policyExpressionSemantics",
        "globalRegionTable", "preflightTaskSchedule", "spsBuild",
    }
    if required_payloads.issubset(decoded_inputs):
        policy = decoded_inputs["policy"]
        abi = decoded_inputs["abi"]
        profile = decoded_inputs["profileConfiguration"]
        if (
            decoded_inputs["policyReviewConfiguration"] != policy["releasePolicyReviewConfig"]
            or decoded_inputs["publicBounds"]["bounds"] != policy["publicBounds"]
            or decoded_inputs["preconditions"]["predicates"] != policy["preconditions"]
            or decoded_inputs["allocaSizeBindings"]["bindings"] != policy["allocaSizeBindings"]
            or decoded_inputs["aliasTopology"]["selectedTopologyIds"]
            != policy["publicAliasTopologyIds"]
            or decoded_inputs["aliasTopology"]["bindings"] != abi["aliasTopologyBindings"]
            or decoded_inputs["policyExpressionSemantics"]
            != decoded_inputs["releaseTable"]["expressionSemantics"]
            or any(
                entry[0]["deterministicSemantics"]
                != decoded_inputs["policyExpressionSemantics"]
                for entry in release_table_entries(decoded_inputs["releaseTable"])
            )
            or decoded_inputs["spsBuild"]["transitionRuleTableDigest"]
            != value["transitionRuleTable"]["sha256"]
            or profile["globalRegionTableDigest"] != value["globalRegionTable"]["sha256"]
            or profile["preflightTaskScheduleDigest"]
            != value["preflightTaskSchedule"]["sha256"]
            or profile["publicAliasTopologyDigest"] != value["aliasTopology"]["sha256"]
        ):
            append_failure(failures, "XF-IDENTITY-001")
    for rule in release_binding_failures(
        value["releaseMarkerBindings"], value["releaseMarkerMachineMap"],
        release_table_value,
    ):
        append_failure(failures, rule)
    return failures


def report_receipts(report: Any) -> list[str]:
    receipts = [report["runEvidence"]["receiptId"]]
    status = report["modelStatus"]
    if status["tag"] == "Counterexample":
        receipts.append(status["args"][0])
    for row in report["queryResults"]:
        outcome = row["outcome"]
        if outcome["tag"] == "NotConstructedV2":
            receipts.append(outcome["protectedEvidence"]["receiptId"])
        else:
            receipts.append(outcome["args"][0]["protectedEvidence"]["receiptId"])
    receipts.extend(row["protectedEvidence"]["receiptId"] for row in report["preflightSummaries"])
    return receipts


def contains_stale_v2_carrier_reason(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("reasonClassId") == "ReleaseConformanceMismatch":
            return True
        return any(contains_stale_v2_carrier_reason(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_stale_v2_carrier_reason(item) for item in value)
    return False


def query_disposition_is_legal(query: Any, artifact: Any) -> bool:
    kind = query["queryKind"]["tag"]
    raw = artifact["rawSolverResult"]
    disposition = artifact["queryDisposition"]
    tag = disposition["tag"]
    existential = {"AdmissionNonempty", "HighVariation"}
    safety = kind not in {*existential, "ReleaseActivation"}
    if raw == "SAT":
        if safety:
            return tag == "CandidateOnly"
        if kind in existential:
            return tag in {"ValidatedExistentialWitness", "Unknown"}
        return tag in {"ValidatedExistentialWitness", "Unknown"}
    if raw == "UNSAT":
        if safety:
            return tag == "Discharged"
        if kind == "AdmissionNonempty":
            return tag == "Unknown" and disposition["args"][0]["reasonClassId"] == "VacuousAdmission"
        if kind == "HighVariation":
            return tag in {"ConstrainedOrUnexercised", "Unknown"}
        return tag in {"Discharged", "Unknown"}
    return raw == "UNKNOWN" and tag == "Unknown"


def query_result_closes_gate(query: Any, outcome: Any) -> bool:
    if outcome["tag"] != "Constructed":
        return False
    artifact = outcome["args"][0]
    if not query_disposition_is_legal(query, artifact):
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


def report_model_gates_closed(report: Any) -> bool:
    queries = report["querySchedule"]["queries"]
    results = report["queryResults"]
    return (
        len(queries) == len(results)
        and all(
            row["queryOrdinal"] == index
            and query_result_closes_gate(queries[index], row["outcome"])
            for index, row in enumerate(results)
        )
        and report["policyReviewStatus"]["tag"] != "Incomplete"
    )


def public_report_failures(report: Any) -> list[str]:
    failures: list[str] = []
    schedule = report["querySchedule"]
    results = report["queryResults"]
    schedule_ok = (
        schedule["artifactIdentityDigest"] == report["artifactIdentityDigest"]
        and schedule["proofConfigurationDigest"] == report["proofConfigurationDigest"]
        and report["queryScheduleDigest"] == exact_digest(schedule)
        and len(schedule["queries"]) == len(results)
        and [row["queryOrdinal"] for row in results] == list(range(len(results)))
        and query_schedule_is_complete(schedule["queries"])
    )
    for index, row in enumerate(results):
        if row["outcome"]["tag"] == "Constructed":
            schedule_ok = schedule_ok and (
                row["outcome"]["args"][0]["proofConfigurationDigest"]
                == report["proofConfigurationDigest"]
            )
            if index < len(schedule["queries"]):
                schedule_ok = schedule_ok and query_disposition_is_legal(
                    schedule["queries"][index], row["outcome"]["args"][0]
                )
    schedule_ok = schedule_ok and all(
        row["artifactIdentityDigest"] == report["artifactIdentityDigest"]
        for row in report["preflightSummaries"]
    )
    review = report["releasePolicyReview"]
    schedule_ok = schedule_ok and (
        review["artifactIdentityDigest"] == report["artifactIdentityDigest"]
        and review["status"] == report["policyReviewStatus"]
    )
    if report["modelStatus"]["tag"] == "Proved" and not report_model_gates_closed(report):
        schedule_ok = False
    if not schedule_ok or contains_stale_v2_carrier_reason(report):
        append_failure(failures, "XF-REPORT-003")
    receipts = report_receipts(report)
    if len(receipts) != len(set(receipts)):
        append_failure(failures, "XF-REPORT-002")
    return failures


def accepted_replay_failures(value: Any) -> list[str]:
    failures: list[str] = []
    if value["finalReceiptId"] != value["protectedEvidence"]["receiptId"]:
        append_failure(failures, "XF-REPLAY-002")
    return failures


def aggregation_input_failures(value: Any) -> list[str]:
    failures: list[str] = []
    accepted = value["acceptedBadReplay"]["tag"] == "Some"
    replay = value["acceptedBadReplay"].get("value")
    invalidating = any(row["scope"] == "ReplayInvalidating" for row in value["blockers"])
    if accepted and invalidating:
        append_failure(failures, "XF-REPLAY-001")
    if accepted:
        for rule in accepted_replay_failures(replay):
            append_failure(failures, rule)
        if (
            replay["artifactIdentityDigest"] != value["artifactIdentityDigest"]
            or replay["proofConfigurationDigest"] != value["proofConfigurationDigest"]
            or replay["queryScheduleDigest"] != value["queryScheduleDigest"]
        ):
            append_failure(failures, "XF-REPLAY-002")
    if not accepted and not value["blockers"] and not value["allRequiredGatesClosed"]:
        append_failure(failures, "XF-AGG-001")
    if value["blockers"] and value["allRequiredGatesClosed"]:
        append_failure(failures, "XF-AGG-001")
    wrong_reason_arm = any(
        (row["scope"] == "RunFinalization")
        != (row["reason"]["tag"] == "ReportingBlocker")
        for row in value["blockers"]
    )
    if wrong_reason_arm:
        append_failure(failures, "XF-AGG-002")
    return failures


def aggregation_decision_failures(value: Any) -> list[str]:
    evidence = value["identityEvidence"]
    identity = evidence["artifactIdentity"]
    input_value = value["input"]
    failures = identity_evidence_failures(evidence)
    for rule in aggregation_input_failures(input_value):
        append_failure(failures, rule)
    if (
        input_value["artifactIdentityDigest"] != evidence["artifactIdentityDigest"]
        or input_value["proofConfigurationDigest"] != identity["proofConfigurationDigest"]
    ):
        append_failure(failures, "XF-IDENTITY-001")
    run = value["runReport"]
    if run["tag"] == "CompletedV2":
        for rule in public_report_failures(run["report"]):
            append_failure(failures, rule)
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
            append_failure(failures, "XF-REPORT-003")
        if report["querySchedule"]["queries"] != evidence["proofConfiguration"]["requiredQuerySchedule"]["queries"]:
            append_failure(failures, "XF-REPORT-003")
        try:
            preflight = require_canonical(bytes.fromhex(
                evidence["preflightTaskSchedule"]["canonicalBytes"]))
            required_task_ids = [task["taskId"] for task in preflight["tasks"]]
        except (KeyError, TypeError, ValueError):
            required_task_ids = []
        summaries = report["preflightSummaries"]
        preflight_closed = (
            [row["taskId"] for row in summaries] == required_task_ids
            and all(
                row["artifactIdentityDigest"] == report["artifactIdentityDigest"]
                for row in summaries
            )
        )
        computed_gates_closed = report_model_gates_closed(report) and preflight_closed
        if input_value["allRequiredGatesClosed"] != computed_gates_closed:
            append_failure(failures, "XF-AGG-001")
        accepted = input_value["acceptedBadReplay"]
        if accepted["tag"] == "Some":
            replay = accepted["value"]
            queries = report["querySchedule"]["queries"]
            if replay["queryOrdinal"] >= len(queries) or queries[replay["queryOrdinal"]] != replay["query"]:
                append_failure(failures, "XF-REPLAY-002")
    try:
        outcome = aggregation_outcome(input_value)
    except ValueError:
        return failures
    expected_matches = False
    if outcome == "ReportingFailedV2":
        expected_matches = run["tag"] == "ReportingFailedV2"
        if expected_matches:
            first = next(row for row in input_value["blockers"] if row["scope"] == "RunFinalization")
            expected_matches = run["report"]["reason"] == first["reason"]["reason"]
    elif run["tag"] == "CompletedV2":
        report = run["report"]
        expected_matches = (
            report["artifactIdentityDigest"] == input_value["artifactIdentityDigest"]
            and report["proofConfigurationDigest"] == input_value["proofConfigurationDigest"]
            and report["queryScheduleDigest"] == input_value["queryScheduleDigest"]
        )
        status = report["modelStatus"]
        if outcome == "Counterexample":
            replay = input_value["acceptedBadReplay"]["value"]
            expected_matches = expected_matches and status == OrderedDict([
                ("tag", "Counterexample"), ("args", [replay["finalReceiptId"]]),
            ])
            if not expected_matches:
                append_failure(failures, "XF-REPLAY-002")
        elif outcome == "Proved":
            expected_matches = expected_matches and status == OrderedDict([("tag", "Proved")])
        elif outcome.startswith("Unknown("):
            reason = outcome.removeprefix("Unknown(").removesuffix(")")
            expected_matches = expected_matches and status == OrderedDict([
                ("tag", "Unknown"),
                ("args", [OrderedDict([("reasonClassId", reason)])]),
            ])
    if not expected_matches:
        append_failure(failures, "XF-AGG-001")
    return failures


def semantic_failures(value: Any, root: str) -> list[str]:
    if root == "AcceptedBadReplayV2":
        return accepted_replay_failures(value)
    if root == "AggregationInputV2":
        return aggregation_input_failures(value)
    if root == "AggregationDecisionV2":
        return aggregation_decision_failures(value)
    if root == "ReleaseMarkerBindingArtifactV2":
        return release_binding_failures(value)
    if root == "ReleaseMarkerMachineMapV2":
        failures: list[str] = []
        rows = value["rows"]
        for field in ["emitMarkerInstructionId", "mirPseudoId", "p4BoundaryId"]:
            values = [row[field] for row in rows]
            if len(values) != len(set(values)):
                append_failure(failures, "XF-INTRINSIC-001")
        return failures
    if root == "ProofConfigurationV2":
        return proof_configuration_failures(value)
    if root == "ArtifactIdentityEvidenceV2":
        return identity_evidence_failures(value)
    if root == "SPSLLVMNFManifestV2":
        failures = identity_evidence_failures(value["artifactIdentityEvidence"])
        identity = value["artifactIdentity"]
        evidence = value["artifactIdentityEvidence"]
        if identity != evidence["artifactIdentity"]:
            append_failure(failures, "XF-IDENTITY-001")
        for field in [
            "releaseMarkerBindingsDigest", "releaseMarkerMachineMapDigest",
            "intrinsicDefinitionDigest", "aggregationSemanticsDigest",
            "replayAcceptanceSemanticsDigest",
        ]:
            if value[field] != identity[field]:
                append_failure(failures, "XF-IDENTITY-001")
        return failures
    if root == "SPSPublicReportV2":
        return public_report_failures(value)
    if root == "SPSRunReportV2" and value["tag"] == "CompletedV2":
        return public_report_failures(value["report"])
    return []


def aggregation_outcome(value: Any) -> str:
    failures = semantic_failures(value, "AggregationInputV2")
    if failures:
        raise ValueError("invalid aggregation input: " + ",".join(failures))
    finalization = [row for row in value["blockers"] if row["scope"] == "RunFinalization"]
    if finalization:
        return "ReportingFailedV2"
    if value["acceptedBadReplay"]["tag"] == "Some":
        return "Counterexample"
    blockers = value["blockers"]
    if len(blockers) > 1:
        return "Unknown(OpenModelObligations)"
    if len(blockers) == 1:
        return "Unknown(" + blockers[0]["reason"]["reason"]["reasonClassId"] + ")"
    if value["allRequiredGatesClosed"]:
        return "Proved"
    raise ValueError("aggregation input has neither result nor blocker")


def generated_files() -> tuple[dict[str, bytes], dict[str, bytes]]:
    validate_policy_expression_grammar()
    defs = all_defs()
    bundle_schema = OrderedDict([
        ("$schema", SCHEMA_DRAFT), ("$id", BUNDLE_ID),
        ("title", "SPS Rev4.1 complete interface definition bundle"),
        ("$defs", defs),
    ])
    source: dict[str, bytes] = {
        "source/schemas/sps-rev4.1.bundle.schema.json": pretty_bytes(bundle_schema),
        "source/interface-registry.json": pretty_bytes(registry()),
    }
    dist: dict[str, bytes] = {
        "dist/schemas/sps-rev4.1.bundle.schema.json": canonical_bytes(bundle_schema),
        "dist/interface-registry.json": canonical_bytes(registry()),
    }
    bundled_schemas: list[Any] = [bundle_schema]
    for filename, (schema_id, roots) in ROOTS.items():
        wrapper = wrapper_schema(schema_id, roots)
        source[f"source/schemas/{filename}"] = pretty_bytes(wrapper)
        dist[f"dist/schemas/{filename}"] = canonical_bytes(wrapper)
        bundled_schemas.append(wrapper)

    catalog_rows = []
    for path, (root, expectation, value, rule) in vector_objects().items():
        source[f"source/vectors/{path}"] = pretty_bytes(value)
        dist[f"dist/vectors/{path}"] = canonical_bytes(value)
        row = OrderedDict([("path", path), ("rootType", root), ("expectation", expectation)])
        if rule is not None:
            row["semanticRuleId"] = rule
        catalog_rows.append(row)
    raw_rows = [OrderedDict([
        ("vectorId", vector_id), ("rootType", root),
        ("encodingBase64", base64.b64encode(raw).decode("ascii")),
        ("expectation", expectation),
    ]) for vector_id, root, raw, expectation in RAW_CASES]
    catalog = OrderedDict([
        ("formatId", "SPS-Interface-Vector-Catalog-v2"),
        ("schemaSetId", SCHEMA_SET_ID), ("fileVectors", catalog_rows),
        ("rawCanonicalVectors", raw_rows),
    ])
    source["source/vectors/vector-catalog.json"] = pretty_bytes(catalog)
    dist["dist/vectors/vector-catalog.json"] = canonical_bytes(catalog)

    dist_bundle = OrderedDict([
        ("formatId", "SPS-Interface-Bundle-v2"), ("schemaSetId", SCHEMA_SET_ID),
        ("specRevision", "4.1"), ("schemas", bundled_schemas),
        ("registry", registry()), ("vectorCatalog", catalog),
    ])
    dist["dist/sps-rev4.1.bundle.json"] = canonical_bytes(dist_bundle)
    return source, dist


def manifest_for(dist: dict[str, bytes]) -> OrderedDict[str, Any]:
    files = [OrderedDict([("path", path.removeprefix("dist/")), ("sha256", sha256(raw))])
             for path, raw in sorted(dist.items())]
    return OrderedDict([
        ("formatId", "SPS-Interface-Manifest-v2"), ("schemaSetId", SCHEMA_SET_ID),
        ("specRevision", "4.1"), ("sourceRevision", SOURCE_REVISION),
        ("bundle", OrderedDict([
            ("path", "sps-rev4.1.bundle.json"),
            ("sha256", sha256(dist["dist/sps-rev4.1.bundle.json"])),
        ])),
        ("rootSchemaIds", OrderedDict((name, schema_id) for name, (schema_id, _) in ROOTS.items())),
        ("files", files),
    ])


def validate_vectors(dist_dir: Path) -> None:
    overlapping_closure = [
        principals for _coalition_id, principals in derived_adversary_coalitions([
            ["principal.alice", "principal.bob"],
            ["principal.bob", "principal.carol"],
        ])
    ]
    if overlapping_closure != [
        ["principal.alice", "principal.bob"],
        ["principal.alice"],
        ["principal.bob", "principal.carol"],
        ["principal.bob"],
        ["principal.carol"],
        [],
    ]:
        raise ValueError(
            "derived coalition closure is not canonical, complete, and deduplicated")
    catalog_raw = (dist_dir / "vectors/vector-catalog.json").read_bytes()
    catalog = require_canonical(catalog_raw)
    for row in catalog["fileVectors"]:
        raw = (dist_dir / "vectors" / row["path"]).read_bytes()
        value = require_canonical(raw)
        error: Exception | None = None
        try:
            validate_root(value, row["rootType"])
        except ValueError as exc:
            error = exc
        expectation = row["expectation"]
        if expectation == "schema-invalid":
            if error is None:
                raise ValueError(f"{row['path']}: expected schema rejection")
            continue
        if error is not None:
            raise ValueError(f"{row['path']}: unexpected schema failure: {error}")
        failures = semantic_failures(value, row["rootType"])
        if expectation == "semantic-invalid":
            if failures != [row["semanticRuleId"]]:
                raise ValueError(f"{row['path']}: semantic failures {failures}")
        elif failures:
            raise ValueError(f"{row['path']}: unexpected semantic failures {failures}")
        if row["path"] == "canonical-valid/coalition-closure-identity-evidence.v2.json":
            queries = value["proofConfiguration"]["requiredQuerySchedule"]["queries"]
            expected_audit_ids = {
                sha256(canonical_bytes(coalition))
                for coalition in [
                    [], ["principal.alice"], ["principal.bob"],
                    ["principal.alice", "principal.bob"],
                ]
            }
            audit_ids = [
                query["coalitionScope"]["coalitionId"]
                for query in queries
                if query["queryKind"]["tag"] == "AuditAll"
            ]
            if len(audit_ids) != 4 or set(audit_ids) != expected_audit_ids:
                raise ValueError(f"{row['path']}: incomplete derived coalition closure")
            joint_id = sha256(canonical_bytes(
                ["principal.alice", "principal.bob"]))
            high_ids = [
                query["coalitionScope"]["coalitionId"]
                for query in queries
                if query["queryKind"]["tag"] == "HighVariation"
            ]
            if (
                len(high_ids) != 3
                or set(high_ids) != expected_audit_ids - {joint_id}
            ):
                raise ValueError(
                    f"{row['path']}: minimally-joint visibility did not suppress "
                    "only the joint HighVariation row")
        if row["rootType"] == "AggregationInputV2" and expectation == "valid":
            expected_outcomes = {
                "canonical-valid/replay-with-proof-blocker.v2.json": "Counterexample",
                "canonical-valid/all-gates-closed.v2.json": "Proved",
                "canonical-valid/run-finalization-failure.v2.json": "ReportingFailedV2",
                "canonical-valid/fp-invalidating-blocker.v2.json": "Unknown(PONFFPArithmeticUnsupported)",
                "canonical-valid/multiple-model-blockers.v2.json": "Unknown(OpenModelObligations)",
            }
            if aggregation_outcome(value) != expected_outcomes[row["path"]]:
                raise ValueError(f"{row['path']}: aggregation outcome mismatch")

    for row in catalog["rawCanonicalVectors"]:
        raw = base64.b64decode(row["encodingBase64"], validate=True)
        parsed_error: Exception | None = None
        value: Any = None
        try:
            value = require_canonical(raw)
        except ValueError as exc:
            parsed_error = exc
        if row["expectation"] == "valid":
            if parsed_error is not None:
                raise ValueError(f"raw {row['vectorId']}: {parsed_error}")
            validate_root(value, row["rootType"])
        elif row["expectation"] == "schema-invalid":
            if parsed_error is not None:
                raise ValueError(f"raw {row['vectorId']}: expected schema-only rejection, got {parsed_error}")
            try:
                validate_root(value, row["rootType"])
            except ValueError:
                pass
            else:
                raise ValueError(f"raw {row['vectorId']}: expected schema rejection")
        elif parsed_error is None:
            raise ValueError(f"raw {row['vectorId']}: expected canonical/parse rejection")


def verify_dist(dist_dir: Path, manifest_path: Path) -> None:
    manifest = require_canonical(manifest_path.read_bytes())
    validate_record(manifest, "SPSInterfaceManifestV2")
    listed: set[str] = set()
    for row in manifest["files"]:
        path = row["path"]
        if path in listed:
            raise ValueError(f"duplicate manifest path: {path}")
        listed.add(path)
        raw = (dist_dir / path).read_bytes()
        if sha256(raw) != row["sha256"]:
            raise ValueError(f"manifest digest mismatch: {path}")
        require_canonical(raw)
    actual = {str(path.relative_to(dist_dir)) for path in dist_dir.rglob("*") if path.is_file()}
    if actual != listed:
        raise ValueError(f"manifest file closure mismatch: listed={sorted(listed)}, actual={sorted(actual)}")
    actual_dist = {
        "dist/" + relative: (dist_dir / relative).read_bytes()
        for relative in sorted(actual)
    }
    expected_manifest = manifest_for(actual_dist)
    if manifest != expected_manifest:
        raise ValueError("interface manifest fields/order/digests are not the exact Rev4.1 manifest")
    expected_dist = generated_files()[1]
    if set(actual_dist) != set(expected_dist):
        raise ValueError("distribution is not the complete Rev4.1 file closure")
    for path, expected_raw in expected_dist.items():
        if actual_dist[path] != expected_raw:
            raise ValueError(f"distribution file is not the pinned Rev4.1 artifact: {path.removeprefix('dist/')}")
    bundle_row = manifest["bundle"]
    if bundle_row["path"] not in listed or sha256((dist_dir / bundle_row["path"]).read_bytes()) != bundle_row["sha256"]:
        raise ValueError("bundle manifest binding mismatch")
    registry_value = require_canonical((dist_dir / "interface-registry.json").read_bytes())
    for key in ["records", "unions", "enums", "formatLiterals", "rootSchemaIds", "semanticRules"]:
        if key not in registry_value:
            raise ValueError(f"registry missing {key}")
    ids: set[str] = set()
    for schema_path in (dist_dir / "schemas").glob("*.json"):
        schema = require_canonical(schema_path.read_bytes())
        if schema.get("$schema") != SCHEMA_DRAFT or not isinstance(schema.get("$id"), str):
            raise ValueError(f"invalid schema declaration: {schema_path.name}")
        ids.add(schema["$id"])
    for schema_path in (dist_dir / "schemas").glob("*.json"):
        schema = require_canonical(schema_path.read_bytes())
        stack = [schema]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                ref = item.get("$ref")
                if isinstance(ref, str) and ref.split("#", 1)[0] not in ids:
                    raise ValueError(f"external or missing schema ref in {schema_path.name}: {ref}")
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)


def write_outputs(root: Path) -> None:
    source, dist = generated_files()
    outputs = dict(source)
    outputs.update(dist)
    outputs["interface-manifest.json"] = canonical_bytes(manifest_for(dist))
    for relative, raw in outputs.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def check_outputs(root: Path) -> None:
    source, dist = generated_files()
    expected = dict(source)
    expected.update(dist)
    expected["interface-manifest.json"] = canonical_bytes(manifest_for(dist))
    for relative, raw in expected.items():
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing generated interface file: {relative}")
        if path.read_bytes() != raw:
            raise ValueError(f"generated interface drift: {relative}")
    verify_dist(root / "dist", root / "interface-manifest.json")
    validate_vectors(root / "dist")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--check", action="store_true", help="check tracked outputs (default)")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check-dist", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        if args.check_dist is not None:
            manifest = args.manifest or args.check_dist.parent / "interface-manifest.json"
            verify_dist(args.check_dist, manifest)
            validate_vectors(args.check_dist)
            print(f"SPS Rev4.1 dist validation: PASSED ({args.check_dist})")
            return 0
        if args.write:
            write_outputs(args.root)
        check_outputs(args.root)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(f"SPS Rev4.1 interface check: FAILED: {exc}", file=sys.stderr)
        return 1
    print("SPS Rev4.1 interface check: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
