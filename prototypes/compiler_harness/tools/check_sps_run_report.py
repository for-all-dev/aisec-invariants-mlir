#!/usr/bin/env python3
"""Validate one canonical `SPSRunReportV1` arm against a harness matcher.

Scope of this tool. It checks *wire form and closed-record shape* of a machine
report, plus the two derivations that are computable from declared inputs
alone: the canonical query-schedule digest and the exact `ReleasePolicyLintV1`
list. It executes no relational semantics, parses no bitcode, and validates no
receipt against a restricted store. A `0` exit therefore says the bytes are a
well-formed report of the requested arm; it never says `NFConforms`, and it
never upgrades a fixture's `ModelStatus` from matcher text to a result.

Normative sources (Rev4 normative specification):
  * section 2.1  `CanonInterfaceJSONV1` wire rules and constructor encoding;
  * section 12   the four `ReleasePolicyLintClass` predicates and scopes;
  * section 19   every record schema, the query scope matrix, the schedule
                 digest, one-result-row-per-ordinal, and the policy-review
                 status rule.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------
# Closed enumerations copied verbatim from the specification.
# --------------------------------------------------------------------------

QUERY_KINDS = (
    "AuditAll",
    "ReleaseConformance",
    "AdmissionNonempty",
    "HighVariation",
    "ReleaseActivation",
    "LLVMDefinedness",
    "Initialization",
    "BoundAdequacy",
    "StructuralAlloca",
    "OutputClosure",
    "CouplingTotality",
    "CouplingFiberTotal",
    "CouplingSymmetry",
    "CouplingSchedulePreservation",
)

# section 19 query scope matrix: every other scope option is exactly None.
SCOPE_MATRIX = {
    "AuditAll": ("entry", "coalition"),
    "ReleaseConformance": ("entry", "release"),
    "ReleaseActivation": ("entry", "release"),
    "AdmissionNonempty": ("entry",),
    "LLVMDefinedness": ("entry",),
    "Initialization": ("entry",),
    "BoundAdequacy": ("entry",),
    "StructuralAlloca": ("entry",),
    "OutputClosure": ("entry",),
    "HighVariation": ("entry", "coalition", "component"),
    "CouplingTotality": ("entry", "coalition", "relation"),
    "CouplingFiberTotal": ("entry", "coalition", "relation"),
    "CouplingSymmetry": ("entry", "coalition", "relation"),
    "CouplingSchedulePreservation": ("entry", "coalition", "relation"),
}

LINT_CLASSES = (
    "IdentityReleaseOfHigh",
    "WorldAudienceContributionOverThreshold",
    "ExpectedVariableDeclaredWorldVisible",
    "CoalitionEntryTotalOverThreshold",
)

CONFIGURATION_REJECTION_REASONS = (
    "NoncanonicalInterface",
    "MissingRequiredIdentity",
    "UnsupportedInterfaceVersion",
    "InterfaceDigestMismatch",
    "ArtifactParseFailure",
    "InsufficientEvidenceCapacity",
)

REPORTING_FAILURE_REASONS = (
    "RestrictedStoreUnavailable",
    "EvidenceFinalizationFailure",
)

RUN_ARMS = ("CompletedV1", "ConfigurationRejectedV1", "ReportingFailedV1")

# A rejection or reporting failure "deliberately contains no input-derived
# digest, path, parser message, byte count, receipt, or ModelStatus".
NONCLAIM_FORBIDDEN_KEYS = (
    "modelStatus",
    "deploymentStatus",
    "policyReviewStatus",
    "artifactIdentityDigest",
    "proofConfigurationDigest",
    "querySchedule",
    "queryScheduleDigest",
    "queryResults",
    "preflightTaskScheduleDigest",
    "preflightSummaries",
    "releasePolicyReview",
    "runEvidence",
    "statusNoninterference",
    "receiptId",
    "protectedEvidence",
    "digest",
    "canonicalBitcodeHash",
    "path",
    "artifactPath",
    "sourcePath",
    "bytes",
    "byteCount",
    "parserMessage",
    "diagnostic",
)

HEX_256 = re.compile(r"[0-9a-f]{64}")
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}")


# --------------------------------------------------------------------------
# Declared per-record field-order tables (section 19 display order).
#
# These tables are the single source of truth for both the recursive exact-key
# check and the canonical rebuild, so canonicality is decided by the schema and
# never by the order the fixture happened to be authored in.
# --------------------------------------------------------------------------

DIGEST = ("digest",)
RECEIPT = ("receipt",)
IDENT = ("id",)
NAT = ("nat",)
POSNAT = ("pos",)
BOOL = ("bool",)
STR = ("str",)
OPAQUE = ("opaque",)


def rec(name: str) -> tuple[str, str]:
    return ("rec", name)


def sum_(name: str) -> tuple[str, str]:
    return ("sum", name)


def lst(item: tuple) -> tuple:
    return ("list", item)


def opt(item: tuple) -> tuple:
    return ("opt", item)


RECORDS: dict[str, tuple[tuple[str, tuple], ...]] = {
    "QueryDescriptorV1": (
        ("queryKind", sum_("QueryKindV1")),
        ("entryScope", opt(IDENT)),
        ("coalitionScope", sum_("CoalitionScopeV1")),
        ("releaseScope", opt(IDENT)),
        ("componentScope", opt(IDENT)),
        ("relationScope", opt(IDENT)),
    ),
    "PublicQueryScheduleV1": (
        ("formatId", ("lit", "SPS-Public-Query-Schedule-v1")),
        ("artifactIdentityDigest", DIGEST),
        ("proofConfigurationDigest", DIGEST),
        ("queries", lst(rec("QueryDescriptorV1"))),
    ),
    "PublicQueryResultRowV1": (
        ("queryOrdinal", NAT),
        ("outcome", sum_("PublicQueryOutcomeV1")),
    ),
    "OptionV1": (
        ("name", STR),
        ("value", OPAQUE),
    ),
    "ResourceLimitsV1": (
        ("maxCallDepth", NAT),
        ("maxLoopCopies", NAT),
        ("maxExpandedInstructions", NAT),
        ("maxPaths", NAT),
        ("maxBytes", NAT),
        ("maxSolverMilliseconds", NAT),
        ("maxSolverMemoryBytes", NAT),
        ("maxEvidenceBytesPerBundle", POSNAT),
        ("maxRestrictedDiagnosticBytes", NAT),
    ),
    "SolverIdentityV1": (
        ("solverName", STR),
        ("solverVersion", STR),
        ("solverBuildDigest", DIGEST),
        ("exactSolverOptions", lst(rec("OptionV1"))),
        ("resourceLimits", rec("ResourceLimitsV1")),
    ),
    "PONFResultArtifactV1": (
        ("formatId", ("lit", "SPS-PONF-Result-v1")),
        ("canonicalPONFDigest", DIGEST),
        ("exactFormulaDigest", DIGEST),
        ("proofConfigurationDigest", DIGEST),
        ("solver", rec("SolverIdentityV1")),
        ("rawSolverResult", ("enum", ("SAT", "UNSAT", "UNKNOWN"))),
        ("protectedEvidence", rec("ProtectedEvidenceReferenceV1")),
        ("queryDisposition", sum_("QueryDispositionV1")),
    ),
    "ProtectedEvidenceReferenceV1": (
        ("receiptId", RECEIPT),
        ("sensitivity", ("lit", "SecretBearing")),
        ("storageClass", ("lit", "RestrictedVerifierStore")),
    ),
    "PreflightTriageSummaryV1": (
        ("artifactIdentityDigest", DIGEST),
        ("taskId", IDENT),
        ("disposition", ("lit", "NonAuthoritativePreflightOnly")),
        ("protectedEvidence", rec("ProtectedEvidenceReferenceV1")),
    ),
    "PublicDispositionReasonV1": (("reasonClassId", IDENT),),
    "ReleasePolicyReviewSummandV1": (
        ("entryId", IDENT),
        ("coalitionId", DIGEST),
        ("releaseId", IDENT),
        ("audienceApplies", BOOL),
        ("disposition", sum_("ReleaseReviewDispositionV1")),
        ("reviewMultiplicity", NAT),
        ("declaredRangeCardinality", POSNAT),
        ("contributionBits", NAT),
    ),
    "ReleasePolicyReviewTotalV1": (
        ("entryId", IDENT),
        ("coalitionId", DIGEST),
        ("totalBits", NAT),
    ),
    "ReleasePolicyLintV1": (
        ("lintClass", ("enum", LINT_CLASSES)),
        ("entryScope", opt(IDENT)),
        ("coalitionScope", sum_("CoalitionScopeV1")),
        ("releaseScope", opt(IDENT)),
        ("componentScope", opt(IDENT)),
    ),
    "ReleasePolicyReviewReportV1": (
        ("formatId", ("lit", "SPS-Release-Policy-Review-v1")),
        ("artifactIdentityDigest", DIGEST),
        ("policyDigest", DIGEST),
        ("releaseDigest", DIGEST),
        ("policyReviewConfigurationDigest", DIGEST),
        ("summands", lst(rec("ReleasePolicyReviewSummandV1"))),
        ("totals", lst(rec("ReleasePolicyReviewTotalV1"))),
        ("lints", lst(rec("ReleasePolicyLintV1"))),
        ("status", sum_("PolicyReviewStatus")),
    ),
    "SPSPublicReportV1": (
        ("formatId", ("lit", "SPS-Public-Report-v1")),
        ("artifactIdentityDigest", DIGEST),
        ("proofConfigurationDigest", DIGEST),
        ("querySchedule", rec("PublicQueryScheduleV1")),
        ("queryScheduleDigest", DIGEST),
        ("queryResults", lst(rec("PublicQueryResultRowV1"))),
        ("preflightTaskScheduleDigest", DIGEST),
        ("preflightSummaries", lst(rec("PreflightTriageSummaryV1"))),
        ("modelStatus", sum_("ModelStatus")),
        ("deploymentStatus", sum_("DeploymentStatus")),
        ("policyReviewStatus", sum_("PolicyReviewStatus")),
        ("releasePolicyReview", rec("ReleasePolicyReviewReportV1")),
        ("runEvidence", rec("ProtectedEvidenceReferenceV1")),
        (
            "statusNoninterference",
            ("lit", "PolicyReviewDoesNotAffectModelOrDeploymentV1"),
        ),
    ),
    "SPSConfigurationRejectionReportV1": (
        ("formatId", ("lit", "SPS-Configuration-Rejection-v1")),
        ("disposition", ("lit", "NoModelStatus")),
        ("reason", sum_("ConfigurationRejectionReasonV1")),
    ),
    "SPSReportingFailureReportV1": (
        ("formatId", ("lit", "SPS-Reporting-Failure-v1")),
        ("disposition", ("lit", "NoModelStatus")),
        ("reason", sum_("SPSReportingFailureReasonV1")),
    ),
}

# Union constructors. `nullary` is `{"tag":"C"}`, `args` is
# `{"tag":"C","args":[...]}`, and `fields` is a displayed record body.
UNIONS: dict[str, dict[str, tuple]] = {
    "QueryKindV1": {kind: ("nullary",) for kind in QUERY_KINDS},
    "CoalitionScopeV1": {
        "None": ("nullary",),
        "ConcreteCoalition": ("fields", (("coalitionId", DIGEST),)),
    },
    "PublicQueryOutcomeV1": {
        "NotConstructedV1": (
            "fields",
            (
                ("reason", rec("PublicDispositionReasonV1")),
                ("protectedEvidence", rec("ProtectedEvidenceReferenceV1")),
            ),
        ),
        "Constructed": ("args", (rec("PONFResultArtifactV1"),)),
    },
    "QueryDispositionV1": {
        "CandidateOnly": ("nullary",),
        "ValidatedExistentialWitness": ("nullary",),
        "ConstrainedOrUnexercised": ("nullary",),
        "Discharged": ("nullary",),
        "Unknown": ("args", (rec("PublicDispositionReasonV1"),)),
    },
    "ReleaseReviewDispositionV1": {
        "ValidatedDormantZero": ("nullary",),
        "ValidatedNotApplicableZero": ("nullary",),
        "ExactAdmittedMaximum": ("nullary",),
        "ConservativeDeclaredCap": ("args", (rec("PublicDispositionReasonV1"),)),
    },
    "ModelStatus": {
        "Proved": ("nullary",),
        "Counterexample": ("args", (RECEIPT,)),
        "Unknown": ("args", (rec("PublicDispositionReasonV1"),)),
    },
    "DeploymentStatus": {
        "Open": ("args", (sum_("P4OpenReasonV1"),)),
        "Closed": ("args", (OPAQUE,)),
    },
    "P4OpenReasonV1": {"P4EvidenceProfileUnavailable": ("nullary",)},
    "PolicyReviewStatus": {
        "Complete": ("nullary",),
        "Findings": ("args", (lst(rec("ReleasePolicyLintV1")),)),
        "Incomplete": ("args", (rec("PublicDispositionReasonV1"),)),
    },
    "ConfigurationRejectionReasonV1": {
        reason: ("nullary",) for reason in CONFIGURATION_REJECTION_REASONS
    },
    "SPSReportingFailureReasonV1": {
        reason: ("nullary",) for reason in REPORTING_FAILURE_REASONS
    },
    "SPSRunReportV1": {
        "ConfigurationRejectedV1": (
            "fields",
            (("report", rec("SPSConfigurationRejectionReportV1")),),
        ),
        "ReportingFailedV1": (
            "fields",
            (("report", rec("SPSReportingFailureReportV1")),),
        ),
        "CompletedV1": ("fields", (("report", rec("SPSPublicReportV1")),)),
    },
}

REPORT_FIELDS = tuple(name for name, _ in RECORDS["SPSPublicReportV1"])


def fail(message: str) -> None:
    raise SystemExit(message)


# --------------------------------------------------------------------------
# Canonical JSON helpers.
# --------------------------------------------------------------------------


def canonical_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_text(value).encode("utf-8")).hexdigest()


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def read_report_json(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_text()
        value = json.loads(raw, object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"invalid report JSON: {error}")
    if not isinstance(value, dict):
        fail("SPSRunReportV1 must be a tagged object")
    return raw, value


# --------------------------------------------------------------------------
# Recursive schema validation and schema-ordered canonical rebuild.
# --------------------------------------------------------------------------


def require_exact_keys(value: dict[str, Any], keys: tuple[str, ...], name: str) -> None:
    if tuple(value) != keys:
        fail(f"{name} fields/order mismatch: {tuple(value)!r}")


def validate_shape(value: Any, schema: tuple, name: str) -> None:
    """Recursively enforce the declared key set and key order.

    A position whose declared type is scalar but whose value is an object is
    deliberately left alone here: the later semantic pass owns that diagnostic
    (for example a `Counterexample` argument that is a witness object rather
    than a receipt string).
    """
    kind = schema[0]
    if kind == "rec":
        fields = RECORDS[schema[1]]
        if not isinstance(value, dict):
            return
        require_exact_keys(value, tuple(f for f, _ in fields), name or schema[1])
        for field, field_schema in fields:
            validate_shape(value[field], field_schema, f"{name}.{field}")
        return
    if kind == "sum":
        variants = UNIONS[schema[1]]
        if not isinstance(value, dict):
            return
        tag = value.get("tag")
        if not isinstance(tag, str):
            fail(f"{name} must be a tagged object with a literal tag field")
        if tag not in variants:
            fail(
                f"{name} tag {tag!r} is outside the closed {schema[1]} constructors: "
                f"{sorted(variants)}"
            )
        variant = variants[tag]
        if variant[0] == "nullary":
            require_exact_keys(value, ("tag",), f"{name} {tag}")
            return
        if variant[0] == "args":
            require_exact_keys(value, ("tag", "args"), f"{name} {tag}")
            args = value["args"]
            if not isinstance(args, list) or len(args) != len(variant[1]):
                fail(
                    f"{name} {tag} must carry exactly {len(variant[1])} positional "
                    "argument(s)"
                )
            for index, (arg, arg_schema) in enumerate(zip(args, variant[1])):
                validate_shape(arg, arg_schema, f"{name} {tag}.args[{index}]")
            return
        fields = variant[1]
        require_exact_keys(
            value, ("tag",) + tuple(f for f, _ in fields), f"{name} {tag}"
        )
        for field, field_schema in fields:
            validate_shape(value[field], field_schema, f"{name} {tag}.{field}")
        return
    if kind == "opt":
        if not isinstance(value, dict):
            return
        tag = value.get("tag")
        if tag == "None":
            require_exact_keys(value, ("tag",), f"{name} None")
            return
        if tag == "Some":
            require_exact_keys(value, ("tag", "value"), f"{name} Some")
            validate_shape(value["value"], schema[1], f"{name}.value")
            return
        fail(f"{name} must be exactly {{'tag':'None'}} or {{'tag':'Some','value':...}}")
    if kind == "list":
        if not isinstance(value, list):
            fail(f"{name} must be an ordered JSON array")
        for index, item in enumerate(value):
            validate_shape(item, schema[1], f"{name}[{index}]")
        return
    if kind == "lit":
        if value != schema[1]:
            fail(f"{name} must be the literal {schema[1]!r}, got {value!r}")
        return
    if kind == "enum":
        if value not in schema[1]:
            fail(f"{name} must be one of {list(schema[1])}, got {value!r}")
        return
    if kind in {"digest", "receipt"}:
        if isinstance(value, str) and not HEX_256.fullmatch(value):
            fail(f"{name} is not 64 lowercase hexadecimal characters")
        return
    if kind == "id":
        if isinstance(value, str) and not IDENTIFIER.fullmatch(value):
            fail(f"{name} is not a canonical identifier")
        return
    if kind in {"nat", "pos"}:
        if not isinstance(value, int) or isinstance(value, bool):
            fail(f"{name} must be a minimal decimal natural")
        if value < 0 or (kind == "pos" and value < 1):
            fail(f"{name} is out of range")
        return
    if kind == "bool":
        if not isinstance(value, bool):
            fail(f"{name} must be a JSON boolean")
        return
    if kind == "str":
        if not isinstance(value, str):
            fail(f"{name} must be a JSON string")
        return


def rebuild(value: Any, schema: tuple) -> Any:
    """Re-emit `value` in declared schema order.

    Serializing this rebuild (rather than the parsed dict) is what makes the
    canonicality comparison a real order check: the parsed dict preserves the
    author's insertion order, the rebuild does not.
    """
    kind = schema[0]
    if kind == "rec":
        fields = RECORDS[schema[1]]
        if isinstance(value, dict) and set(value) == {f for f, _ in fields}:
            return {f: rebuild(value[f], t) for f, t in fields}
        return rebuild_unschemad(value)
    if kind == "sum":
        variants = UNIONS[schema[1]]
        if isinstance(value, dict) and value.get("tag") in variants:
            variant = variants[value["tag"]]
            if variant[0] == "nullary" and set(value) == {"tag"}:
                return {"tag": value["tag"]}
            if variant[0] == "args" and set(value) == {"tag", "args"}:
                args = value["args"]
                if isinstance(args, list) and len(args) == len(variant[1]):
                    return {
                        "tag": value["tag"],
                        "args": [rebuild(a, t) for a, t in zip(args, variant[1])],
                    }
            if variant[0] == "fields":
                fields = variant[1]
                if set(value) == {"tag"} | {f for f, _ in fields}:
                    out = {"tag": value["tag"]}
                    for field, field_schema in fields:
                        out[field] = rebuild(value[field], field_schema)
                    return out
        return rebuild_unschemad(value)
    if kind == "opt":
        if isinstance(value, dict) and set(value) == {"tag", "value"}:
            return {"tag": value["tag"], "value": rebuild(value["value"], schema[1])}
        return rebuild_unschemad(value)
    if kind == "list":
        if isinstance(value, list):
            return [rebuild(item, schema[1]) for item in value]
        return rebuild_unschemad(value)
    return rebuild_unschemad(value)


def rebuild_unschemad(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: rebuild_unschemad(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rebuild_unschemad(item) for item in value]
    return value


def require_canonical_bytes(raw: str, run: dict[str, Any]) -> None:
    canonical = canonical_text(rebuild(run, sum_("SPSRunReportV1")))
    if raw not in {canonical, canonical + "\n"}:
        fail("report is not compact canonical JSON or has noncanonical field order")


# --------------------------------------------------------------------------
# Small semantic helpers retained from the original checker.
# --------------------------------------------------------------------------


def check_receipt(value: Any, name: str) -> str:
    if not isinstance(value, str) or not HEX_256.fullmatch(value):
        fail(f"{name} is not a random-receipt-shaped 256-bit lowercase hex value")
    return value


def check_model_status(actual: Any, matcher: dict[str, Any]) -> str | None:
    if not isinstance(actual, dict):
        fail("modelStatus must be a tagged object")
    tag = matcher["tag"]
    if tag == "Proved":
        if actual != {"tag": "Proved"}:
            fail(f"expected modelStatus Proved, got {actual!r}")
        return None
    if tag == "Unknown":
        if actual != matcher:
            fail(f"expected modelStatus {matcher!r}, got {actual!r}")
        return None
    if tag != "Counterexample":
        fail(f"unsupported ModelStatus matcher: {tag}")
    require_exact_keys(actual, ("tag", "args"), "Counterexample")
    args = actual.get("args")
    if actual.get("tag") != "Counterexample" or not isinstance(args, list) or len(args) != 1:
        fail("Counterexample must carry exactly one positional receiptId")
    return check_receipt(args[0], "Counterexample receiptId")


# --------------------------------------------------------------------------
# Query schedule.
# --------------------------------------------------------------------------


def coalition_id(principals: list[str]) -> str:
    """`CoalitionId(A) = SHA256(CanonCoalitionV1(A))` (specification section 1)."""
    return canonical_digest(sorted(set(principals)))


def scope_present(scope: Any) -> bool:
    return isinstance(scope, dict) and scope.get("tag") not in {"None", None}


def descriptor_sort_key(descriptor: dict[str, Any]) -> tuple[int, bytes]:
    kind = descriptor["queryKind"]["tag"]
    scope_bytes = canonical_text(
        [
            descriptor["entryScope"],
            descriptor["coalitionScope"],
            descriptor["releaseScope"],
            descriptor["componentScope"],
            descriptor["relationScope"],
        ]
    ).encode("utf-8")
    return (QUERY_KINDS.index(kind), scope_bytes)


def check_query_schedule(report: dict[str, Any], case: dict[str, Any]) -> None:
    schedule = report["querySchedule"]
    if schedule["artifactIdentityDigest"] != report["artifactIdentityDigest"]:
        fail("querySchedule.artifactIdentityDigest must equal the report identity digest")
    if schedule["proofConfigurationDigest"] != report["proofConfigurationDigest"]:
        fail(
            "querySchedule.proofConfigurationDigest must equal the report "
            "proof-configuration digest"
        )

    queries = schedule["queries"]
    if not queries:
        fail("PublicQueryScheduleV1.queries must contain every required descriptor once")

    seen: set[str] = set()
    for index, descriptor in enumerate(queries):
        text = canonical_text(descriptor)
        if text in seen:
            fail(f"querySchedule.queries[{index}] duplicates an earlier descriptor")
        seen.add(text)
        kind = descriptor["queryKind"]["tag"]
        required = SCOPE_MATRIX[kind]
        for field, label in (
            ("entryScope", "entry"),
            ("coalitionScope", "coalition"),
            ("releaseScope", "release"),
            ("componentScope", "component"),
            ("relationScope", "relation"),
        ):
            present = scope_present(descriptor[field])
            if present != (label in required):
                fail(
                    f"querySchedule.queries[{index}] violates the {kind} scope matrix: "
                    f"{field} must be {'non-None' if label in required else 'None'}"
                )
        if "coalition" in required and descriptor["coalitionScope"]["tag"] != (
            "ConcreteCoalition"
        ):
            fail(f"querySchedule.queries[{index}] needs a concrete coalition scope")

    ordered = sorted(queries, key=descriptor_sort_key)
    if [canonical_text(q) for q in queries] != [canonical_text(q) for q in ordered]:
        fail(
            "querySchedule.queries is not ordered by QueryKindV1 ordinal then "
            "canonical scope bytes"
        )

    expected_digest = canonical_digest(rebuild(schedule, rec("PublicQueryScheduleV1")))
    if report["queryScheduleDigest"] != expected_digest:
        fail(
            "queryScheduleDigest is not "
            "CanonicalPublicQueryScheduleDigestV1(querySchedule)"
        )

    rows = report["queryResults"]
    if len(rows) != len(queries):
        fail(
            f"queryResults has {len(rows)} rows for {len(queries)} scheduled "
            "descriptors; exactly one row per schedule ordinal is required"
        )
    for index, row in enumerate(rows):
        if row["queryOrdinal"] != index:
            fail(
                f"queryResults[{index}].queryOrdinal is {row['queryOrdinal']!r}; rows "
                "must appear in numeric schedule-ordinal order"
            )

    check_audit_all_agreement(queries, rows, case)


def check_audit_all_agreement(
    queries: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    case: dict[str, Any],
) -> None:
    """Bind the AuditAll descriptors to the harness case catalog.

    This is a fixture-consistency check against a `claimable: false` matcher
    catalog, not a semantic result.
    """
    expectations = case.get("audit_all_expectations", [])
    expected = {}
    for expectation in expectations:
        entry = expectation["entry"]
        expected[(entry, coalition_id(expectation["coalition"]))] = expectation

    scheduled = {}
    for index, descriptor in enumerate(queries):
        if descriptor["queryKind"]["tag"] != "AuditAll":
            continue
        key = (
            descriptor["entryScope"]["value"],
            descriptor["coalitionScope"]["coalitionId"],
        )
        scheduled[key] = index

    if set(scheduled) != set(expected):
        fail(
            "scheduled AuditAll (entry, CoalitionId) pairs do not match the case "
            f"catalog: {len(scheduled)} scheduled, {len(expected)} expected"
        )

    for key, index in scheduled.items():
        matcher = expected[key]["query_outcome_matcher"]
        outcome = rows[index]["outcome"]
        if matcher["tag"] == "NotConstructedResultMatcherV1":
            if outcome["tag"] != "NotConstructedV1":
                fail(
                    f"queryResults[{index}] must be NotConstructedV1 to match the case "
                    "matcher"
                )
            if outcome["reason"] != matcher["reason"]:
                fail(
                    f"queryResults[{index}] NotConstructedV1 reason "
                    f"{outcome['reason']!r} disagrees with the case matcher "
                    f"{matcher['reason']!r}"
                )
            continue
        if matcher["tag"] != "ConstructedResultMatcherV1":
            fail(f"unsupported AuditAll outcome matcher: {matcher['tag']!r}")
        if outcome["tag"] != "Constructed":
            fail(
                f"queryResults[{index}] must be Constructed to match the case matcher"
            )
        artifact = outcome["args"][0]
        if artifact["rawSolverResult"] != matcher["raw_solver_result"]:
            fail(
                f"queryResults[{index}] rawSolverResult "
                f"{artifact['rawSolverResult']!r} disagrees with the case matcher "
                f"{matcher['raw_solver_result']!r}"
            )
        if artifact["queryDisposition"] != matcher["query_disposition"]:
            fail(
                f"queryResults[{index}] queryDisposition disagrees with the case "
                f"matcher {matcher['query_disposition']!r}"
            )


# --------------------------------------------------------------------------
# Release policy review.
# --------------------------------------------------------------------------


def load_policy_release(root: Path) -> dict[str, Any]:
    path = root / "sps" / "Inputs" / "lecture-policy-release.json"
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        fail(f"cannot read the harness lecture policy/release input: {error}")
    if value.get("formatId") != "SPS-Harness-Lecture-Policy-Release-v1":
        fail("lecture policy/release input has the wrong harness formatId")
    return value


def initially_visible(policy: dict[str, Any], component: str, coalition: list[str]) -> bool:
    """`DEF-VISIBLE` specialized to `M.componentVisibility`."""
    basis = policy["componentVisibility"]
    if component in basis["worldVisible"]:
        return True
    for principal in coalition:
        if component in basis["memberVisible"].get(principal, []):
            return True
    for joint in basis["minimallyJointVisible"]:
        if set(joint["principals"]) <= set(coalition) and joint["item"] == component:
            return True
    return False


def audience_applies(release: dict[str, Any], coalition: list[str]) -> bool:
    """`Audience(q,A)` (specification section 12)."""
    basis = release["audience"]
    if basis["worldVisible"]:
        return True
    if set(basis["memberVisible"]) & set(coalition):
        return True
    return any(set(joint) <= set(coalition) for joint in basis["minimallyJointVisible"])


def exceeds(bits: int, threshold: dict[str, int]) -> bool:
    """`NaturalExceedsRationalV1(x,r) = (x * r.denominator) > r.numerator`."""
    return bits * threshold["denominator"] > threshold["numerator"]


def some(value: str) -> dict[str, Any]:
    return {"tag": "Some", "value": value}


NONE_SCOPE = {"tag": "None"}


def concrete_coalition(principals: list[str]) -> dict[str, Any]:
    return {"tag": "ConcreteCoalition", "coalitionId": coalition_id(principals)}


def lint(
    lint_class: str,
    entry: Any,
    coalition_scope: dict[str, Any],
    release: Any,
    component: Any,
) -> dict[str, Any]:
    return {
        "lintClass": lint_class,
        "entryScope": entry,
        "coalitionScope": coalition_scope,
        "releaseScope": release,
        "componentScope": component,
    }


def derive_expected_lints(
    policy: dict[str, Any],
    case_id: str,
    entry: str,
    review: dict[str, Any],
) -> list[dict[str, Any]]:
    """Derive the exact `ReleasePolicyLintV1` list from declared inputs.

    The two capacity classes are defined by the specification over the report's
    own unique summand/total rows, so they read `review`; the two structural
    classes read only the policy and release declarations. Nothing here mirrors
    a lecture `expected.logical.yaml`, which self-declares
    `normativeInterface: false`.
    """
    threshold = policy["capacityWarningThresholdBits"]
    coalitions = policy["derivedCoalitions"]
    bound = policy["caseReleaseBindings"].get(case_id)
    if bound is None:
        fail(f"lecture policy/release input has no release binding for {case_id}")
    releases = [(rid, policy["releases"][rid]) for rid in sorted(bound)]
    components = sorted(policy["components"])

    found: list[dict[str, Any]] = []

    # IdentityReleaseOfHigh
    for coalition in coalitions:
        for release_id, release in releases:
            for component in components:
                identity_ref = release["identityComponentRef"]
                if identity_ref.get("tag") != "Some" or identity_ref["value"] != component:
                    continue
                if not audience_applies(release, coalition):
                    continue
                if initially_visible(policy, component, coalition):
                    continue  # Class_A(c) = Low
                found.append(
                    lint(
                        "IdentityReleaseOfHigh",
                        some(entry),
                        concrete_coalition(coalition),
                        some(release_id),
                        some(component),
                    )
                )

    # WorldAudienceContributionOverThreshold
    empty_id = coalition_id([])
    for release_id, release in releases:
        if not release["audience"]["worldVisible"]:
            continue
        summand = find_summand(review, entry, empty_id, release_id)
        if summand is not None and exceeds(summand["contributionBits"], threshold):
            found.append(
                lint(
                    "WorldAudienceContributionOverThreshold",
                    some(entry),
                    NONE_SCOPE,
                    some(release_id),
                    NONE_SCOPE,
                )
            )

    # ExpectedVariableDeclaredWorldVisible
    for assertion in policy["expectedVariableAssertions"]:
        if assertion["entry"] != entry:
            continue
        if assertion["component"] in policy["componentVisibility"]["worldVisible"]:
            found.append(
                lint(
                    "ExpectedVariableDeclaredWorldVisible",
                    some(entry),
                    concrete_coalition(assertion["coalition"]),
                    NONE_SCOPE,
                    some(assertion["component"]),
                )
            )

    # CoalitionEntryTotalOverThreshold
    for coalition in coalitions:
        total = find_total(review, entry, coalition_id(coalition))
        if total is not None and exceeds(total["totalBits"], threshold):
            found.append(
                lint(
                    "CoalitionEntryTotalOverThreshold",
                    some(entry),
                    concrete_coalition(coalition),
                    NONE_SCOPE,
                    NONE_SCOPE,
                )
            )

    unique: dict[str, dict[str, Any]] = {}
    for item in found:
        unique[canonical_text(item)] = item
    return sorted(
        unique.values(),
        key=lambda item: (
            LINT_CLASSES.index(item["lintClass"]),
            canonical_text(
                [
                    item["entryScope"],
                    item["coalitionScope"],
                    item["releaseScope"],
                    item["componentScope"],
                ]
            ).encode("utf-8"),
        ),
    )


def find_summand(
    review: dict[str, Any], entry: str, coalition: str, release: str
) -> dict[str, Any] | None:
    for row in review["summands"]:
        if (row["entryId"], row["coalitionId"], row["releaseId"]) == (
            entry,
            coalition,
            release,
        ):
            return row
    return None


def find_total(review: dict[str, Any], entry: str, coalition: str) -> dict[str, Any] | None:
    for row in review["totals"]:
        if (row["entryId"], row["coalitionId"]) == (entry, coalition):
            return row
    return None


def check_review_rows(
    policy: dict[str, Any], case_id: str, entry: str, review: dict[str, Any]
) -> None:
    coalitions = policy["derivedCoalitions"]
    releases = sorted(policy["caseReleaseBindings"][case_id])

    expected_summands = [
        (entry, coalition_id(coalition), release)
        for coalition in coalitions
        for release in releases
    ]
    expected_summands.sort()
    actual_summands = [
        (row["entryId"], row["coalitionId"], row["releaseId"])
        for row in review["summands"]
    ]
    if actual_summands != expected_summands:
        fail(
            "releasePolicyReview.summands must be the entry x derived-coalition x "
            "release product in canonical id order"
        )

    expected_totals = sorted(
        (entry, coalition_id(coalition)) for coalition in coalitions
    )
    actual_totals = [(row["entryId"], row["coalitionId"]) for row in review["totals"]]
    if actual_totals != expected_totals:
        fail(
            "releasePolicyReview.totals must contain every (entry, coalition) pair "
            "exactly once in canonical id order"
        )


def check_policy_review(
    actual: Any,
    matcher: dict[str, Any],
    expected_lints: list[dict[str, Any]],
    review_lints: list[dict[str, Any]],
) -> None:
    if review_lints != expected_lints:
        fail(
            "releasePolicyReview.lints is not the exact ordered lint set derived from "
            f"the policy and release declarations: expected {len(expected_lints)} "
            f"row(s), got {len(review_lints)}"
        )

    if not expected_lints:
        if actual != {"tag": "Complete"}:
            fail(f"an empty lint list requires PolicyReviewStatus Complete, got {actual!r}")
        if matcher != {"tag": "Complete"}:
            fail(f"case matcher expected {matcher!r} but the derived lint set is empty")
        return

    if actual == {"tag": "Complete"}:
        fail("PolicyReviewStatus Complete requires lints == []")
    if not isinstance(actual, dict) or tuple(actual) != ("tag", "args"):
        fail("Findings must use the canonical positional constructor")
    args = actual.get("args")
    if actual.get("tag") != "Findings" or not isinstance(args, list) or len(args) != 1:
        fail("Findings must carry exactly one finite-set argument")
    if args[0] != expected_lints:
        fail("Findings(S) must carry exactly the derived ReleasePolicyLintV1 set")

    if matcher.get("tag") != "FindingsMatcherV1":
        fail(f"unsupported policy-review matcher: {matcher!r}")
    actual_classes = sorted({item["lintClass"] for item in expected_lints})
    required = sorted(set(matcher["required_lint_classes"]))
    if actual_classes != required:
        fail(
            f"policy lint classes {actual_classes} are not exactly the case matcher "
            f"classes {required}"
        )


# --------------------------------------------------------------------------
# Non-claim arms.
# --------------------------------------------------------------------------


def reject_claim_bearing_content(value: Any, arm: str, path: str = "report") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in NONCLAIM_FORBIDDEN_KEYS:
                fail(
                    f"{arm} must not carry an input-derived or status-bearing "
                    f"{key!r} field ({path}.{key})"
                )
            reject_claim_bearing_content(item, arm, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            reject_claim_bearing_content(item, arm, f"{path}[{index}]")
        return
    if isinstance(value, str) and HEX_256.fullmatch(value):
        fail(f"{arm} must not carry a digest- or receipt-shaped value ({path})")


def check_nonclaim_arm(run: dict[str, Any], arm: str) -> None:
    report = run["report"]
    reject_claim_bearing_content(report, arm)
    if report["disposition"] != "NoModelStatus":
        fail(
            f"{arm} disposition must be the literal \"NoModelStatus\", got "
            f"{report['disposition']!r}"
        )
    reason = report["reason"]["tag"]
    print(f"verified {arm}: disposition NoModelStatus, reason {reason}")


# --------------------------------------------------------------------------


def load_case(root: Path, case_id: str) -> dict[str, Any]:
    path = root / "integration" / "Inputs" / "sps-lecture" / "cases.json"
    catalog = json.loads(path.read_text())
    for case in catalog.get("cases", []):
        if case.get("case_id") == case_id:
            return case
    fail(f"unknown lecture case: {case_id}")


def check_completed(root: Path, case_id: str, run: dict[str, Any]) -> None:
    case = load_case(root, case_id)
    report = run["report"]
    require_exact_keys(report, REPORT_FIELDS, "SPSPublicReportV1")

    for digest_field in (
        "artifactIdentityDigest",
        "proofConfigurationDigest",
        "queryScheduleDigest",
        "preflightTaskScheduleDigest",
    ):
        check_receipt(report[digest_field], digest_field)

    check_query_schedule(report, case)

    counterexample_receipt = check_model_status(
        report["modelStatus"], case["expected_model_status_matcher"]
    )
    if report["deploymentStatus"] != case["expected_deployment_status"]:
        fail("deploymentStatus does not match the base-profile expectation")

    review = report["releasePolicyReview"]
    if review["status"] != report["policyReviewStatus"]:
        fail("releasePolicyReview.status must equal policyReviewStatus")
    if review["artifactIdentityDigest"] != report["artifactIdentityDigest"]:
        fail(
            "releasePolicyReview.artifactIdentityDigest must equal the report identity "
            "digest"
        )

    entries = sorted(
        {row["entryId"] for row in review["totals"]}
        | {
            descriptor["entryScope"]["value"]
            for descriptor in report["querySchedule"]["queries"]
            if descriptor["entryScope"]["tag"] == "Some"
        }
    )
    if len(entries) != 1:
        fail(f"the lecture fixtures declare exactly one closed entry, got {entries!r}")
    entry = entries[0]

    policy = load_policy_release(root)
    check_review_rows(policy, case_id, entry, review)
    expected_lints = derive_expected_lints(policy, case_id, entry, review)
    check_policy_review(
        report["policyReviewStatus"],
        case["expected_policy_review_status_matcher"],
        expected_lints,
        review["lints"],
    )

    run_evidence = report["runEvidence"]
    run_receipt = check_receipt(run_evidence["receiptId"], "runEvidence receiptId")
    if counterexample_receipt == run_receipt:
        fail("final counterexample and completed-run evidence receipts must be fresh")

    print(f"verified {case_id}: canonical CompletedV1 SPSRunReportV1")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--expect-arm",
        choices=RUN_ARMS,
        default="CompletedV1",
        help=(
            "which SPSRunReportV1 constructor this invocation accepts; the default "
            "keeps every existing caller CompletedV1-only"
        ),
    )
    args = parser.parse_args()

    raw, run = read_report_json(args.report)
    require_exact_keys(run, ("tag", "report"), "SPSRunReportV1")
    if run["tag"] != args.expect_arm:
        fail(
            f"expected SPSRunReportV1 arm {args.expect_arm}, got {run['tag']!r}"
        )
    if not isinstance(run["report"], dict):
        fail(f"{args.expect_arm} must carry one tagged report object")

    if args.expect_arm != "CompletedV1":
        reject_claim_bearing_content(run["report"], args.expect_arm)

    validate_shape(run, sum_("SPSRunReportV1"), "SPSRunReportV1")
    require_canonical_bytes(raw, run)

    if args.expect_arm == "CompletedV1":
        if not args.case:
            fail("--case is required for the CompletedV1 arm")
        check_completed(args.root.resolve(), args.case, run)
        return

    check_nonclaim_arm(run, args.expect_arm)


if __name__ == "__main__":
    main()
