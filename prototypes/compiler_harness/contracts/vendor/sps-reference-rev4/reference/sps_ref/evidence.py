"""Canonical witness-free evidence for the executable relation reference."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .canonical import canonical_bytes, canonical_digest, load_json_bytes
from .counterexample import (
    load_counterexample_pair,
    validate_and_replay_counterexample_pair,
)
from .engine import compile_program
from .errors import ReferenceError, SchemaError, SolverUnavailableError
from .model import parse_coalition, parse_program, require_exact_keys, require_identifier
from .ponf import audit_reference_ponf, build_reference_ponf
from .query import (
    QUERY_KINDS,
    build_reference_query,
    run_concrete_query,
    run_query_exhaustive,
    validate_query_witness,
)
from .replay import replay_witness
from .smt import lower_reference_ponf, lower_reference_query
from .solve import run_cvc5, run_z3


PROFILE_FORMAT = "SPS-Reference-Evidence-Profile-v1"
PROFILE_ID = "SPS-Reference-Relation-v1"
RESULT_FORMAT = "SPS-Reference-Evidence-Result-v1"
DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[1]
    / "profiles"
    / "reference-relation-v1.json"
)
INTEGRITY_CHECKS = (
    "ReferencePONFFieldAudit",
    "ProductAndSerializedPONFLoweringByteMatch",
    "SMTInputDigestMatch",
    "SMTLoweringRepeatability",
)
REQUIRED_LIMITATIONS = (
    "ExecutableReferenceOnly",
    "HandAuthoredReduction",
    "NotFrozenLLVM",
    "ReducedBitWidth",
)
FILE_ROLES = ("abi", "c", "mlir", "policy", "referenceFixture", "snapshot")


def load_reference_profile(path: Path = DEFAULT_PROFILE_PATH) -> dict[str, Any]:
    try:
        value = load_json_bytes(path.read_bytes())
    except OSError as exc:
        raise SchemaError(f"cannot read reference evidence profile: {exc}") from exc
    return validate_reference_profile(value)


def validate_reference_profile(value: Any) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "formatId",
            "profileId",
            "claimBoundary",
            "normativeClaimEffect",
            "queryAnalogues",
            "artifactIntegrityChecks",
            "evaluation",
            "resultFormat",
        },
        "reference profile",
    )
    if (
        value["formatId"] != PROFILE_FORMAT
        or value["profileId"] != PROFILE_ID
        or value["claimBoundary"] != "ExecutableReferenceOnly"
        or value["normativeClaimEffect"] != "None"
        or value["resultFormat"] != RESULT_FORMAT
    ):
        raise SchemaError("unsafe or unknown reference evidence profile")
    rows = value["queryAnalogues"]
    if not isinstance(rows, list) or len(rows) != 4:
        raise SchemaError("reference profile must define four query analogues")
    expected_analogues = [
        (
            "ReferenceAdmissionNonempty",
            "AdmissionNonempty",
            "ReducedFiniteAnalogue",
            ["Conformance Profile 12.4", "Normative 21.5"],
        ),
        (
            "ReferenceHighVariation",
            "HighVariation",
            "ReducedFiniteAnaloguePerHighInput",
            ["Conformance Profile 12.4", "Normative 21.5"],
        ),
        (
            "ReferenceTerminalOutputSurface",
            "OutputClosure",
            "StrictSubsetReturnRootTerminationOnly",
            ["Conformance Profile 12.4", "Normative 21.5"],
        ),
        (
            "ReferenceAuditAll",
            "AuditAll",
            "ReducedFiniteTwoLaneAnalogue",
            ["Conformance Profile 12.4", "Normative 21.5"],
        ),
    ]
    actual_analogues: list[tuple[str, str, str, list[str]]] = []
    for index, row in enumerate(rows):
        require_exact_keys(
            row,
            {"referenceQuery", "analogueOf", "relationship", "requirementRefs"},
            f"reference profile query {index}",
        )
        if row["referenceQuery"] not in QUERY_KINDS:
            raise SchemaError("reference profile contains an unknown query")
        if (
            not isinstance(row["requirementRefs"], list)
            or not row["requirementRefs"]
            or not all(isinstance(item, str) and item for item in row["requirementRefs"])
        ):
            raise SchemaError("reference profile has malformed requirementRefs")
        actual_analogues.append(
            (
                row["referenceQuery"],
                row["analogueOf"],
                row["relationship"],
                row["requirementRefs"],
            )
        )
    if actual_analogues != expected_analogues:
        raise SchemaError("reference profile query analogue definitions differ")
    if tuple(value["artifactIntegrityChecks"]) != INTEGRITY_CHECKS:
        raise SchemaError("reference profile integrity-check inventory differs")
    evaluation = value["evaluation"]
    require_exact_keys(
        evaluation,
        {
            "requiredBackends",
            "optionalBackends",
            "requireAgreement",
            "requireAuditAllSATReplay",
            "requireSATAssignmentValidation",
        },
        "reference profile evaluation",
    )
    if (
        evaluation["requiredBackends"]
        != ["concrete-exhaustive", "symbolic-exhaustive", "z3"]
        or evaluation["optionalBackends"] != ["cvc5"]
        or evaluation["requireAgreement"] is not True
        or evaluation["requireAuditAllSATReplay"] is not True
        or evaluation["requireSATAssignmentValidation"] is not True
    ):
        raise SchemaError("reference profile evaluation policy differs")
    return value


def validate_relation_fixture(value: Any) -> dict[str, Any]:
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
        "relation fixture",
    )
    if value["formatId"] != "SPS-Executable-Reference-Fixture-v3" or value["kind"] != "relation":
        raise SchemaError("external relation fixture has the wrong format or kind")
    for field in ("familyId", "caseId"):
        require_identifier(value[field], f"relation fixture.{field}")
    if (
        not isinstance(value["requirementRefs"], list)
        or not value["requirementRefs"]
        or not all(isinstance(item, str) and item for item in value["requirementRefs"])
    ):
        raise SchemaError("relation fixture requirementRefs are malformed")
    require_exact_keys(value["input"], {"program", "coalition"}, "relation fixture.input")
    program = parse_program(value["input"]["program"], "relation fixture.input.program")
    parse_coalition(value["input"]["coalition"], "relation fixture.input.coalition")
    expected = value["expected"]
    require_exact_keys(
        expected,
        {
            "auditAll",
            "admissionNonempty",
            "highVariation",
            "terminalOutputSurface",
        },
        "relation fixture.expected",
    )
    if expected["admissionNonempty"] != "sat" or expected["terminalOutputSurface"] != "unsat":
        raise SchemaError("relation fixture requires admitted, output-closed controls")
    audit = expected["auditAll"]
    require_exact_keys(audit, {"status", "firstDifference"}, "relation fixture.expected.auditAll")
    if audit["status"] not in {"sat", "unsat"}:
        raise SchemaError("relation fixture AuditAll expectation is invalid")
    difference = audit["firstDifference"]
    if audit["status"] == "unsat":
        if difference is not None:
            raise SchemaError("UNSAT relation fixture cannot name a first difference")
    else:
        require_exact_keys(difference, {"kind", "field"}, "relation fixture firstDifference")
        if (difference["kind"], difference["field"]) not in {
            ("BranchSuccessor", "successor"),
            ("Output", "valueBytes"),
        }:
            raise SchemaError("unsupported relation first-difference locator")
    high = expected["highVariation"]
    if not isinstance(high, list):
        raise SchemaError("relation fixture highVariation must be a list")
    expected_high = sorted(
        item["id"] for item in program["inputs"] if item["classification"] == "High"
    )
    actual_high: list[str] = []
    for index, row in enumerate(high):
        require_exact_keys(row, {"componentId", "status"}, f"highVariation[{index}]")
        if row["status"] != "sat":
            raise SchemaError("relation fixture requires High-variation witnesses")
        actual_high.append(row["componentId"])
    if actual_high != expected_high:
        raise SchemaError("relation fixture High-variation inventory differs")
    return value


def validate_reduction_binding(
    value: Any,
    fixture: Mapping[str, Any],
    *,
    binding_path: Path | None = None,
    fixture_path: Path | None = None,
) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "formatId",
            "harnessCase",
            "referenceCaseId",
            "entry",
            "files",
            "arguments",
            "roots",
            "coalition",
            "observations",
            "limitations",
            "counterexamplePair",
        },
        "reduction binding",
    )
    if value["formatId"] != "SPS-Harness-Reference-Reduction-Binding-v2":
        raise SchemaError("wrong reduction binding format")
    _require_harness_case(value["harnessCase"], "reduction binding.harnessCase")
    for field in ("referenceCaseId", "entry"):
        require_identifier(value[field], f"reduction binding.{field}")
    program = fixture["input"]["program"]
    if value["referenceCaseId"] != fixture["caseId"] or value["entry"] != program["entryId"]:
        raise SchemaError("reduction binding fixture or entry identity differs")
    _validate_file_rows(value["files"], binding_path, fixture_path)
    argument_indices, argument_names, argument_components = _validate_argument_rows(
        value["arguments"], program
    )
    root_indices, root_names, root_components = _validate_root_rows(
        value["roots"], program
    )
    if (
        argument_indices & root_indices
        or argument_names & root_names
        or argument_components & root_components
    ):
        raise SchemaError(
            "binding scalar and root ABI mappings must be disjoint"
        )
    _validate_coalition_mapping(value["coalition"], fixture["input"]["coalition"])
    observations = value["observations"]
    if not isinstance(observations, list):
        raise SchemaError("binding observations must be a list")
    normalized_observations: list[tuple[str, str]] = []
    for index, row in enumerate(observations):
        require_exact_keys(row, {"kind", "field"}, f"binding observation {index}")
        require_identifier(row["kind"], f"binding observation {index}.kind")
        require_identifier(row["field"], f"binding observation {index}.field")
        if (row["kind"], row["field"]) not in {
            ("BranchSuccessor", "successor"),
            ("Output", "valueBytes"),
        }:
            raise SchemaError("binding observation is outside the closed profile")
        normalized_observations.append((row["kind"], row["field"]))
    if normalized_observations != sorted(set(normalized_observations)):
        raise SchemaError("binding observations must be sorted and unique")
    difference = fixture["expected"]["auditAll"]["firstDifference"]
    if difference is not None and (
        difference["kind"], difference["field"]
    ) not in normalized_observations:
        raise SchemaError("binding omits the expected first-difference observation")
    if value["limitations"] != list(REQUIRED_LIMITATIONS):
        raise SchemaError("binding limitations differ from the required exact inventory")
    _validate_counterexample_pair_row(
        value["counterexamplePair"], fixture, binding_path
    )
    return value


def run_relation_fixture(
    fixture: Mapping[str, Any],
    binding: Mapping[str, Any],
    profile_path_or_value: str | Path | Mapping[str, Any] = DEFAULT_PROFILE_PATH,
    *,
    fixture_path: Path | None = None,
    binding_path: Path | None = None,
) -> dict[str, Any]:
    fixture = validate_relation_fixture(dict(fixture))
    profile = _profile_value(profile_path_or_value)
    binding = validate_reduction_binding(
        dict(binding), fixture, binding_path=binding_path, fixture_path=fixture_path
    )
    program = parse_program(fixture["input"]["program"])
    coalition = parse_coalition(fixture["input"]["coalition"])
    left = compile_program(program, "L")
    right = compile_program(program, "R")
    _validate_bound_counterexample_pair(
        fixture,
        binding,
        left,
        right,
        coalition,
        binding_path=binding_path,
    )
    query_specs = [
        ("ReferenceAdmissionNonempty", None),
        *(
            ("ReferenceHighVariation", component)
            for component in sorted(
                item.input_id
                for item in left.inputs
                if item.classification == "High"
            )
        ),
        ("ReferenceTerminalOutputSurface", None),
        ("ReferenceAuditAll", None),
    ]
    rows: list[dict[str, Any]] = []
    for query_kind, component_id in query_specs:
        rows.append(
            _run_query(
                fixture,
                left,
                right,
                coalition,
                query_kind,
                component_id,
            )
        )
    descriptor = {
        "coalitionId": coalition.coalition_id,
        "principals": sorted(coalition.principals),
        "controlledHosts": sorted(coalition.controlled_hosts),
    }
    result: dict[str, Any] = {
        "formatId": RESULT_FORMAT,
        "claimBoundary": "ExecutableReferenceOnly",
        "normativeClaimEffect": "None",
        "profileBinding": {
            "profileId": profile["profileId"],
            "canonicalProfileDigest": canonical_digest(profile),
        },
        "fixtureBinding": {
            "caseId": fixture["caseId"],
            "canonicalFixtureDigest": canonical_digest(fixture),
        },
        "reductionBinding": {
            "harnessCase": binding["harnessCase"],
            "canonicalBindingDigest": canonical_digest(binding),
        },
        "programDigest": canonical_digest(program),
        "coalitionDescriptorDigest": canonical_digest(descriptor),
        "artifactIntegrity": [
            {"checkId": check, "passed": True} for check in INTEGRITY_CHECKS
        ],
        "queries": rows,
    }
    result["canonicalResultDigest"] = canonical_digest(result)
    return validate_relation_result(
        result,
        profile,
        fixture=fixture,
        binding=binding,
        fixture_path=fixture_path,
        binding_path=binding_path,
    )


def validate_relation_result(
    value: Any,
    profile_path_or_value: str | Path | Mapping[str, Any],
    *,
    fixture: Mapping[str, Any] | None = None,
    binding: Mapping[str, Any] | None = None,
    fixture_path: Path | None = None,
    binding_path: Path | None = None,
) -> dict[str, Any]:
    """Validate canonical result shape and, when supplied, its exact context.

    The two-argument form is intentionally structural so stored endpoints can
    be reparsed without sidecars. Supplying both ``fixture`` and ``binding``
    additionally reconstructs the complete query inventory and every PONF/SMT
    digest and binds all top-level identities to that context.
    """

    profile = _profile_value(profile_path_or_value)
    require_exact_keys(
        value,
        {
            "formatId",
            "claimBoundary",
            "normativeClaimEffect",
            "profileBinding",
            "fixtureBinding",
            "reductionBinding",
            "programDigest",
            "coalitionDescriptorDigest",
            "artifactIntegrity",
            "queries",
            "canonicalResultDigest",
        },
        "relation result",
    )
    if (
        value["formatId"] != RESULT_FORMAT
        or value["claimBoundary"] != "ExecutableReferenceOnly"
        or value["normativeClaimEffect"] != "None"
    ):
        raise SchemaError("unsafe relation result claim boundary")
    _validate_digest(value["programDigest"], "programDigest")
    _validate_digest(value["coalitionDescriptorDigest"], "coalitionDescriptorDigest")
    profile_binding = value["profileBinding"]
    require_exact_keys(profile_binding, {"profileId", "canonicalProfileDigest"}, "profile binding")
    if profile_binding != {
        "profileId": profile["profileId"],
        "canonicalProfileDigest": canonical_digest(profile),
    }:
        raise SchemaError("relation result profile binding differs")
    fixture_binding = value["fixtureBinding"]
    require_exact_keys(fixture_binding, {"caseId", "canonicalFixtureDigest"}, "fixture binding")
    require_identifier(fixture_binding["caseId"], "fixture binding.caseId")
    _validate_digest(fixture_binding["canonicalFixtureDigest"], "fixture digest")
    reduction_binding = value["reductionBinding"]
    require_exact_keys(reduction_binding, {"harnessCase", "canonicalBindingDigest"}, "reduction binding")
    _require_harness_case(reduction_binding["harnessCase"], "reduction binding.harnessCase")
    _validate_digest(reduction_binding["canonicalBindingDigest"], "binding digest")
    integrity = value["artifactIntegrity"]
    if integrity != [
        {"checkId": check, "passed": True} for check in INTEGRITY_CHECKS
    ]:
        raise SchemaError("relation result integrity evidence differs")
    rows = value["queries"]
    if not isinstance(rows, list) or not rows:
        raise SchemaError("relation result requires query rows")
    seen: list[tuple[str, str | None]] = []
    for index, row in enumerate(rows):
        _validate_result_query(row, profile, index)
        seen.append((row["queryId"], row["componentId"]))
    expected_order = [
        ("ReferenceAdmissionNonempty", None),
        *sorted(
            (item for item in seen if item[0] == "ReferenceHighVariation"),
            key=lambda item: str(item[1]),
        ),
        ("ReferenceTerminalOutputSurface", None),
        ("ReferenceAuditAll", None),
    ]
    if seen != expected_order or len(seen) != len(set(seen)):
        raise SchemaError("relation result query order or inventory differs")
    digest_preimage = dict(value)
    recorded = digest_preimage.pop("canonicalResultDigest")
    _validate_digest(recorded, "canonicalResultDigest")
    if canonical_digest(digest_preimage) != recorded:
        raise SchemaError("relation result canonical digest mismatch")
    if (fixture is None) != (binding is None):
        raise SchemaError(
            "contextual relation-result validation requires fixture and binding"
        )
    if fixture is not None and binding is not None:
        _validate_relation_result_context(
            value,
            fixture,
            binding,
            fixture_path=fixture_path,
            binding_path=binding_path,
        )
    return value


def project_relation_result(value: Any) -> dict[str, object]:
    """Project only stable semantic facts used by harness snapshot matching."""

    validated = validate_relation_result(value, _profile_from_result(value))
    by_kind = {row["queryId"]: row for row in validated["queries"] if row["queryId"] != "ReferenceHighVariation"}
    high = [
        row["componentId"]
        for row in validated["queries"]
        if row["queryId"] == "ReferenceHighVariation" and row["outcome"] == "sat"
    ]
    audit = by_kind["ReferenceAuditAll"]
    projection: dict[str, object] = {
        "query.admission-nonempty": by_kind["ReferenceAdmissionNonempty"]["outcome"],
        "query.high-variation": high,
        "query.terminal-output-surface": by_kind["ReferenceTerminalOutputSurface"]["outcome"],
        "query.audit-all": audit["outcome"],
        "backend.agreement": all(row["backendAgreement"] for row in validated["queries"]),
    }
    if audit["firstDifference"] is not None:
        projection["query.audit-all-first-difference"] = dict(audit["firstDifference"])
    return projection


def canonical_relation_result_bytes(value: Any) -> bytes:
    """Return the exact newline-free canonical endpoint bytes."""

    validated = validate_relation_result(value, _profile_from_result(value))
    return canonical_bytes(validated)


def _validate_relation_result_context(
    value: Mapping[str, Any],
    raw_fixture: Mapping[str, Any],
    raw_binding: Mapping[str, Any],
    *,
    fixture_path: Path | None,
    binding_path: Path | None,
) -> None:
    fixture = validate_relation_fixture(dict(raw_fixture))
    binding = validate_reduction_binding(
        dict(raw_binding),
        fixture,
        fixture_path=fixture_path,
        binding_path=binding_path,
    )
    program = parse_program(fixture["input"]["program"])
    coalition = parse_coalition(fixture["input"]["coalition"])
    descriptor = {
        "coalitionId": coalition.coalition_id,
        "principals": sorted(coalition.principals),
        "controlledHosts": sorted(coalition.controlled_hosts),
    }
    if value["fixtureBinding"] != {
        "caseId": fixture["caseId"],
        "canonicalFixtureDigest": canonical_digest(fixture),
    }:
        raise SchemaError("relation result differs from its fixture context")
    if value["reductionBinding"] != {
        "harnessCase": binding["harnessCase"],
        "canonicalBindingDigest": canonical_digest(binding),
    }:
        raise SchemaError("relation result differs from its reduction context")
    if value["programDigest"] != canonical_digest(program):
        raise SchemaError("relation result program digest differs from context")
    if value["coalitionDescriptorDigest"] != canonical_digest(descriptor):
        raise SchemaError("relation result coalition digest differs from context")

    left = compile_program(program, "L")
    right = compile_program(program, "R")
    _validate_bound_counterexample_pair(
        fixture,
        binding,
        left,
        right,
        coalition,
        binding_path=binding_path,
    )
    specs = [
        ("ReferenceAdmissionNonempty", None),
        *(
            ("ReferenceHighVariation", item.input_id)
            for item in sorted(left.inputs, key=lambda item: item.input_id)
            if item.classification == "High"
        ),
        ("ReferenceTerminalOutputSurface", None),
        ("ReferenceAuditAll", None),
    ]
    rows = value["queries"]
    actual_inventory = [
        (row["queryId"], row["componentId"]) for row in rows
    ]
    if actual_inventory != specs:
        raise SchemaError(
            "relation result query inventory differs from declared High inputs"
        )
    expected = fixture["expected"]
    high_expected = {
        row["componentId"]: row["status"]
        for row in expected["highVariation"]
    }
    for row, (query_kind, component_id) in zip(rows, specs, strict=True):
        ponf = build_reference_ponf(
            left, right, coalition, query_kind, component_id
        )
        audit_reference_ponf(
            ponf, left, right, coalition, query_kind, component_id
        )
        smt = lower_reference_ponf(ponf)
        if row["ponfDigest"] != ponf["canonicalReferencePONFDigest"]:
            raise SchemaError(
                f"{query_kind}: result PONF digest differs from context"
            )
        if row["exactSMTDigest"] != smt.sha256:
            raise SchemaError(
                f"{query_kind}: result SMT digest differs from context"
            )
        if query_kind == "ReferenceAdmissionNonempty":
            expected_outcome = expected["admissionNonempty"]
        elif query_kind == "ReferenceHighVariation":
            assert component_id is not None
            expected_outcome = high_expected[component_id]
        elif query_kind == "ReferenceTerminalOutputSurface":
            expected_outcome = expected["terminalOutputSurface"]
        else:
            expected_outcome = expected["auditAll"]["status"]
        if row["outcome"] != expected_outcome:
            raise SchemaError(
                f"{query_kind}: result outcome differs from fixture context"
            )
        expected_difference = (
            expected["auditAll"]["firstDifference"]
            if query_kind == "ReferenceAuditAll"
            else None
        )
        if row["firstDifference"] != expected_difference:
            raise SchemaError(
                f"{query_kind}: result first difference differs from context"
            )


def _run_query(fixture, left, right, coalition, query_kind, component_id):
    query = build_reference_query(left, right, coalition, query_kind, component_id)
    ponf = build_reference_ponf(left, right, coalition, query_kind, component_id)
    audit_reference_ponf(ponf, left, right, coalition, query_kind, component_id)
    if canonical_bytes(ponf) != canonical_bytes(
        build_reference_ponf(left, right, coalition, query_kind, component_id)
    ):
        raise SchemaError("nondeterministic reference PONF")
    direct_smt = lower_reference_query(query)
    smt = lower_reference_ponf(ponf)
    if direct_smt != smt or smt != lower_reference_ponf(ponf):
        raise SchemaError("reference direct/PONF lowering mismatch or nondeterminism")
    symbolic = run_query_exhaustive(query)
    concrete = run_concrete_query(query, left, right, coalition)
    z3 = run_z3(smt)
    backend_results = [
        ("symbolic-exhaustive", symbolic),
        ("concrete-exhaustive", concrete),
        ("z3", z3),
    ]
    configured_cvc5 = os.environ.get("CVC5", "")
    if configured_cvc5 or shutil.which("cvc5") is not None:
        backend_results.append(("cvc5", run_cvc5(smt)))
    outcomes = {result.status for _, result in backend_results}
    if len(outcomes) != 1 or outcomes & {"unknown", "error"}:
        raise ReferenceError(
            "reference query backend disagreement: "
            + ", ".join(f"{name}={result.status}" for name, result in backend_results)
        )
    outcome = next(iter(outcomes))
    first_difference = None
    validation_rows: list[dict[str, Any]] = []
    for name, result in sorted(backend_results, key=lambda item: item[0]):
        validated = True
        if outcome == "sat":
            if result.witness is None:
                raise SchemaError(f"{name} omitted its SAT assignment")
            if query_kind == "ReferenceAuditAll":
                replay = replay_witness(left, right, coalition, result.witness)
                validated = replay.accepted
                if validated and first_difference is None:
                    first_difference = _semantic_difference(replay)
            else:
                validated = validate_query_witness(
                    query, left, right, coalition, result.witness
                )
            if not validated:
                raise SchemaError(f"{name} SAT assignment failed independent validation")
        validation_rows.append(
            {"backend": name, "outcome": outcome, "validated": validated}
        )
    expected = fixture["expected"]
    if query_kind == "ReferenceAdmissionNonempty":
        expected_outcome = expected["admissionNonempty"]
    elif query_kind == "ReferenceHighVariation":
        expected_outcome = next(
            row["status"]
            for row in expected["highVariation"]
            if row["componentId"] == component_id
        )
    elif query_kind == "ReferenceTerminalOutputSurface":
        expected_outcome = expected["terminalOutputSurface"]
    else:
        expected_outcome = expected["auditAll"]["status"]
    if outcome != expected_outcome:
        raise SchemaError(
            f"{query_kind}: expected {expected_outcome}, observed {outcome}"
        )
    if query_kind == "ReferenceAuditAll" and first_difference != expected["auditAll"]["firstDifference"]:
        raise SchemaError(
            f"ReferenceAuditAll first difference {first_difference!r} differs from fixture"
        )
    return {
        "queryId": query_kind,
        "componentId": component_id,
        "outcome": outcome,
        "ponfDigest": ponf["canonicalReferencePONFDigest"],
        "exactSMTDigest": smt.sha256,
        "backendAgreement": True,
        "backends": validation_rows,
        "validation": {
            "assignmentValidationRequired": outcome == "sat",
            "allSATAssignmentsValidated": all(row["validated"] for row in validation_rows),
        },
        "firstDifference": first_difference,
    }


def _semantic_difference(replay) -> dict[str, str] | None:
    if not replay.accepted or replay.first_bad_event_ordinal is None:
        return None
    ordinal = replay.first_bad_event_ordinal
    if ordinal >= len(replay.left_trace):
        return {"kind": "Output", "field": "valueBytes"}
    event = replay.left_trace[ordinal]
    if event.kind == "BranchSuccessor":
        return {"kind": "BranchSuccessor", "field": "successor"}
    return {"kind": event.kind, "field": "valueBytes"}


def _validate_result_query(row, profile, index):
    require_exact_keys(
        row,
        {
            "queryId",
            "componentId",
            "outcome",
            "ponfDigest",
            "exactSMTDigest",
            "backendAgreement",
            "backends",
            "validation",
            "firstDifference",
        },
        f"relation result query {index}",
    )
    if row["queryId"] not in QUERY_KINDS or row["outcome"] not in {"sat", "unsat"}:
        raise SchemaError("unknown query or outcome in relation result")
    if (row["queryId"] == "ReferenceHighVariation") != isinstance(row["componentId"], str):
        raise SchemaError("relation result componentId disagrees with query kind")
    _validate_digest(row["ponfDigest"], "ponfDigest")
    _validate_digest(row["exactSMTDigest"], "exactSMTDigest")
    if row["backendAgreement"] is not True:
        raise SchemaError("relation result records backend disagreement")
    backends = row["backends"]
    if not isinstance(backends, list):
        raise SchemaError("relation result backends must be a list")
    names: list[str] = []
    required = set(profile["evaluation"]["requiredBackends"])
    if os.environ.get("CVC5", "") or shutil.which("cvc5") is not None:
        required.add("cvc5")
    allowed = required | set(profile["evaluation"]["optionalBackends"])
    for backend_index, backend in enumerate(backends):
        require_exact_keys(backend, {"backend", "outcome", "validated"}, f"backend {backend_index}")
        if backend["backend"] not in allowed or backend["outcome"] != row["outcome"] or backend["validated"] is not True:
            raise SchemaError("malformed or disagreeing backend evidence")
        names.append(backend["backend"])
    if names != sorted(set(names)) or not required <= set(names):
        raise SchemaError("relation result backend inventory differs")
    validation = row["validation"]
    require_exact_keys(validation, {"assignmentValidationRequired", "allSATAssignmentsValidated"}, "query validation")
    if validation != {
        "assignmentValidationRequired": row["outcome"] == "sat",
        "allSATAssignmentsValidated": True,
    }:
        raise SchemaError("relation result validation summary differs")
    difference = row["firstDifference"]
    if row["queryId"] != "ReferenceAuditAll" or row["outcome"] == "unsat":
        if difference is not None:
            raise SchemaError("only SAT AuditAll may contain a first difference")
    else:
        require_exact_keys(difference, {"kind", "field"}, "result firstDifference")
        if (difference["kind"], difference["field"]) not in {
            ("BranchSuccessor", "successor"),
            ("Output", "valueBytes"),
        }:
            raise SchemaError("relation result first difference is outside the closed vocabulary")


def _validate_counterexample_pair_row(
    row: Any,
    fixture: Mapping[str, Any],
    binding_path: Path | None,
) -> None:
    audit_status = fixture["expected"]["auditAll"]["status"]
    if audit_status == "unsat":
        if row is not None:
            raise SchemaError("UNSAT relation binding requires counterexamplePair: null")
        return
    if row is None:
        raise SchemaError("SAT relation binding requires a counterexample pair")
    require_exact_keys(row, {"path", "sha256"}, "binding counterexamplePair")
    if row["path"] != "counterexample-pair.yaml":
        raise SchemaError("binding counterexamplePair must name the fixed sibling path")
    _validate_digest(row["sha256"], "binding counterexamplePair digest")
    if binding_path is not None:
        raw = _read_counterexample_pair_bytes(row, binding_path)
        # Parse here as part of binding validation; semantic replay follows only
        # after the exact reduced program has been compiled.
        load_counterexample_pair(raw, str(_counterexample_pair_path(binding_path)))


def _counterexample_pair_path(binding_path: Path) -> Path:
    return (binding_path.resolve().parent.parent / "counterexample-pair.yaml").resolve()


def _read_counterexample_pair_bytes(
    row: Mapping[str, Any], binding_path: Path
) -> bytes:
    case_root = binding_path.resolve().parent.parent
    target = _counterexample_pair_path(binding_path)
    try:
        target.relative_to(case_root)
    except ValueError as exc:
        raise SchemaError("counterexample pair resolves outside its case directory") from exc
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise SchemaError(f"cannot read counterexample pair: {exc}") from exc
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise SchemaError("counterexample pair raw-byte digest mismatch")
    return raw


def _validate_bound_counterexample_pair(
    fixture: Mapping[str, Any],
    binding: Mapping[str, Any],
    left,
    right,
    coalition,
    *,
    binding_path: Path | None,
) -> None:
    row = binding["counterexamplePair"]
    if row is None:
        return
    if binding_path is None:
        raise SchemaError(
            "counterexample-pair replay requires the reduction binding path"
        )
    target = _counterexample_pair_path(binding_path)
    pair = load_counterexample_pair(
        _read_counterexample_pair_bytes(row, binding_path), str(target)
    )
    validate_and_replay_counterexample_pair(
        pair, fixture, binding, left, right, coalition
    )


def _validate_file_rows(rows, binding_path, fixture_path):
    if not isinstance(rows, list):
        raise SchemaError("binding files must be a list")
    roles: list[str] = []
    base = binding_path.resolve().parent.parent if binding_path is not None else None
    for index, row in enumerate(rows):
        require_exact_keys(row, {"role", "path", "sha256"}, f"binding file {index}")
        role = row["role"]
        path = row["path"]
        if role not in FILE_ROLES or not isinstance(path, str):
            raise SchemaError("binding file role or path is invalid")
        if role == "snapshot" and path != "snapshot.yaml":
            raise SchemaError(
                "binding snapshot role must name the fixed case-local snapshot.yaml"
            )
        pure = PurePosixPath(path)
        if pure.is_absolute() or str(pure) != path or any(part in {"", ".", ".."} for part in pure.parts):
            raise SchemaError("binding file path is not canonical case-relative POSIX")
        _validate_digest(row["sha256"], f"binding file {role} digest")
        roles.append(role)
        if base is not None:
            target = (base / Path(*pure.parts)).resolve()
            try:
                target.relative_to(base)
            except ValueError as exc:
                raise SchemaError("binding file resolves outside its case directory") from exc
            try:
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
            except OSError as exc:
                raise SchemaError(f"cannot read binding file {path}: {exc}") from exc
            if actual != row["sha256"]:
                raise SchemaError(f"binding file digest mismatch for {role}")
            if role == "referenceFixture" and fixture_path is not None and target != fixture_path.resolve():
                raise SchemaError("binding referenceFixture path differs from CLI fixture")
    if roles != list(FILE_ROLES):
        raise SchemaError("binding file roles must be exact, sorted, and unique")


def _validate_argument_rows(rows, program):
    if not isinstance(rows, list):
        raise SchemaError("binding arguments must be a list")
    by_id = {item["id"]: item for item in program["inputs"]}
    seen: list[str] = []
    components: set[str] = set()
    argument_indices: set[int] = set()
    argument_names: set[str] = set()
    for index, row in enumerate(rows):
        require_exact_keys(
            row,
            {"referenceInput", "component", "argumentIndex", "argumentName", "fullWidth", "reducedWidth", "classification"},
            f"binding argument {index}",
        )
        for field in ("referenceInput", "component", "argumentName"):
            require_identifier(row[field], f"binding argument {index}.{field}")
        if not isinstance(row["argumentIndex"], int) or isinstance(row["argumentIndex"], bool) or row["argumentIndex"] < 0:
            raise SchemaError("binding argument ABI index is invalid")
        item = by_id.get(row["referenceInput"])
        if item is None or row["reducedWidth"] != item["width"] or row["classification"] != item["classification"]:
            raise SchemaError("binding argument disagrees with reference input")
        if not isinstance(row["fullWidth"], int) or isinstance(row["fullWidth"], bool) or row["fullWidth"] < row["reducedWidth"]:
            raise SchemaError("binding argument fullWidth is invalid")
        if (
            row["component"] in components
            or row["argumentIndex"] in argument_indices
            or row["argumentName"] in argument_names
        ):
            raise SchemaError(
                "binding argument components, ABI indices, and names must be unique"
            )
        components.add(row["component"])
        argument_indices.add(row["argumentIndex"])
        argument_names.add(row["argumentName"])
        seen.append(row["referenceInput"])
    if seen != sorted(by_id):
        raise SchemaError("binding arguments must exactly cover sorted reference inputs")
    return argument_indices, argument_names, components


def _validate_root_rows(rows, program):
    if not isinstance(rows, list):
        raise SchemaError("binding roots must be a list")
    by_id = {root["id"]: root for root in program["abi"]["roots"]}
    used_offsets = _program_root_offsets(program)
    seen: list[str] = []
    abi_roots: set[str] = set()
    components: set[str] = set()
    allocation_sites: set[str] = set()
    argument_indices: set[int] = set()
    argument_names: set[str] = set()
    for index, row in enumerate(rows):
        require_exact_keys(
            row,
            {"referenceRoot", "component", "storageKind", "abiRoot", "argumentIndex", "argumentName", "allocationSite", "byteLength", "initialClassification", "terminalVisibility", "offsets"},
            f"binding root {index}",
        )
        require_identifier(row["referenceRoot"], f"binding root {index}.referenceRoot")
        root = by_id.get(row["referenceRoot"])
        if root is None or row["byteLength"] != root["byteLength"]:
            raise SchemaError("binding root disagrees with reference root")
        if row["storageKind"] == "ABIArgument":
            if (
                not isinstance(row["abiRoot"], str)
                or not isinstance(row["component"], str)
                or not isinstance(row["argumentIndex"], int)
                or isinstance(row["argumentIndex"], bool)
                or row["argumentIndex"] < 0
                or not isinstance(row["argumentName"], str)
                or row["allocationSite"] is not None
                or not root["terminalOutput"]
            ):
                raise SchemaError(
                    "ABIArgument mapping has illegal mixed or missing fields"
                )
            require_identifier(row["abiRoot"], f"binding root {index}.abiRoot")
            require_identifier(row["component"], f"binding root {index}.component")
            require_identifier(row["argumentName"], f"binding root {index}.argumentName")
            if row["initialClassification"] not in {"Low", "High"} or row["terminalVisibility"] not in {"Low", "High"}:
                raise SchemaError("ABI root classification is invalid")
            if not all(root["initialized"]):
                raise SchemaError(
                    "classified ABI roots must be fully initialized at entry"
                )
            if (
                row["abiRoot"] in abi_roots
                or row["component"] in components
                or row["argumentIndex"] in argument_indices
                or row["argumentName"] in argument_names
            ):
                raise SchemaError(
                    "binding ABI root IDs, argument indices, and names must be unique"
                )
            abi_roots.add(row["abiRoot"])
            components.add(row["component"])
            argument_indices.add(row["argumentIndex"])
            argument_names.add(row["argumentName"])
        elif row["storageKind"] == "InternalAlloca":
            if (
                row["abiRoot"] is not None
                or row["component"] is not None
                or row["argumentIndex"] is not None
                or row["argumentName"] is not None
                or not isinstance(row["allocationSite"], str)
                or root["terminalOutput"]
            ):
                raise SchemaError("InternalAlloca mapping has illegal mixed or missing fields")
            require_identifier(row["allocationSite"], f"binding root {index}.allocationSite")
            if row["allocationSite"] in allocation_sites:
                raise SchemaError(
                    "binding internal allocation sites must be unique"
                )
            allocation_sites.add(row["allocationSite"])
            if row["initialClassification"] != "Uninitialized" or row["terminalVisibility"] != "NotTerminalOutput":
                raise SchemaError("InternalAlloca state classification is invalid")
            if any(root["initialized"]):
                raise SchemaError(
                    "Uninitialized internal allocations must start wholly uninitialized"
                )
        else:
            raise SchemaError("binding root has unknown storageKind")
        offsets = row["offsets"]
        if not isinstance(offsets, list) or offsets != sorted(set(offsets)) or any(not isinstance(offset, int) or isinstance(offset, bool) or offset < 0 or offset >= root["byteLength"] for offset in offsets):
            raise SchemaError("binding root offsets are invalid")
        if offsets != used_offsets[row["referenceRoot"]]:
            raise SchemaError(
                "binding root offsets differ from reduced-program load/store offsets"
            )
        seen.append(row["referenceRoot"])
    if seen != sorted(by_id):
        raise SchemaError("binding roots must exactly cover sorted reference roots")
    return argument_indices, argument_names, components


def _program_root_offsets(program):
    """Collect exact load/store start offsets from the reduced program."""

    offsets = {root["id"]: set() for root in program["abi"]["roots"]}

    def expression(value):
        if isinstance(value, dict):
            if set(value) == {"load"}:
                payload = value["load"]
                root_id = payload["root"]
                if root_id not in offsets:
                    raise SchemaError(
                        "reduced program load names an undeclared root"
                    )
                offsets[root_id].add(payload["offset"])
            for child in value.values():
                expression(child)
        elif isinstance(value, list):
            for child in value:
                expression(child)

    def statements(rows):
        for statement in rows:
            if statement["op"] == "store":
                root_id = statement["root"]
                if root_id not in offsets:
                    raise SchemaError(
                        "reduced program store names an undeclared root"
                    )
                offsets[root_id].add(statement["offset"])
            for field in ("condition", "guard", "iterations", "value"):
                if field in statement and statement[field] is not None:
                    expression(statement[field])
            for field in ("then", "else", "body"):
                if field in statement:
                    statements(statement[field])

    expression(program["admission"])
    statements(program["statements"])
    return {
        root_id: sorted(root_offsets)
        for root_id, root_offsets in offsets.items()
    }


def _validate_coalition_mapping(value, fixture_coalition):
    require_exact_keys(
        value,
        {
            "referenceCoalitionId",
            "policyAdversaryId",
            "policyAdversaryIndex",
            "principals",
            "controlledHosts",
            "hostMappings",
        },
        "binding coalition",
    )
    require_identifier(
        value["referenceCoalitionId"], "binding coalition.referenceCoalitionId"
    )
    require_identifier(
        value["policyAdversaryId"], "binding coalition.policyAdversaryId"
    )
    if (
        value["referenceCoalitionId"] != fixture_coalition["id"]
        or value["principals"] != sorted(fixture_coalition["principals"])
        or value["controlledHosts"]
        != sorted(fixture_coalition["controlledHosts"])
    ):
        raise SchemaError("binding coalition disagrees with relation fixture")
    if (
        not isinstance(value["policyAdversaryIndex"], int)
        or isinstance(value["policyAdversaryIndex"], bool)
        or value["policyAdversaryIndex"] < 0
    ):
        raise SchemaError("binding coalition policy adversary index is invalid")
    if (
        value["policyAdversaryId"] != "maximal"
        or value["policyAdversaryIndex"] != 0
    ):
        raise SchemaError(
            "reference relation profile requires policy adversary maximal[0]"
        )
    for field in ("principals", "controlledHosts"):
        members = value[field]
        if members != sorted(set(members)):
            raise SchemaError(f"binding coalition {field} must be sorted and unique")
        for index, member in enumerate(members):
            require_identifier(member, f"binding coalition {field}[{index}]")
    mappings = value["hostMappings"]
    if not isinstance(mappings, list):
        raise SchemaError("binding coalition hostMappings must be a list")
    mapped: list[str] = []
    for index, row in enumerate(mappings):
        require_exact_keys(
            row,
            {"referenceHost", "policyHost", "boundaryClass"},
            f"binding coalition host mapping {index}",
        )
        require_identifier(
            row["referenceHost"],
            f"binding coalition host mapping {index}.referenceHost",
        )
        if (
            row["boundaryClass"] != "PublicObservationEndpoint"
            or row["policyHost"] is not None
        ):
            raise SchemaError(
                "reference observer hosts must map to a non-host public observation endpoint"
            )
        mapped.append(row["referenceHost"])
    if mapped != value["controlledHosts"]:
        raise SchemaError(
            "binding coalition must map every controlled reference host exactly once"
        )


def _validate_digest(value, context):
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise SchemaError(f"{context} is not a lowercase SHA-256 digest")


def _require_harness_case(value: Any, context: str) -> None:
    if not isinstance(value, str):
        raise SchemaError(f"{context}: expected precision-control/<case>")
    parts = value.split("/")
    if len(parts) != 2 or parts[0] != "precision-control":
        raise SchemaError(f"{context}: expected precision-control/<case>")
    require_identifier(parts[1], context)


def _profile_value(value):
    if isinstance(value, (str, Path)):
        return load_reference_profile(Path(value))
    return validate_reference_profile(dict(value))


def _profile_from_result(value):
    # Projection is intentionally tied to the installed canonical profile.
    profile = load_reference_profile()
    if isinstance(value, dict) and value.get("profileBinding", {}).get("canonicalProfileDigest") != canonical_digest(profile):
        raise SchemaError("relation result is not bound to the installed profile")
    return profile
