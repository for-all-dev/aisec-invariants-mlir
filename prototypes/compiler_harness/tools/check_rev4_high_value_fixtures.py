#!/usr/bin/env python3
"""Validate Rev. 4 high-value fixture contracts and decisive LLVM shapes.

This is a fixture validator, not the SPS verifier.  It makes the test corpus
executable without promoting any hand-authored expectation to ModelStatus.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from typing import Any

import check_sps_stage_report
import sps_aggregation


def status_matcher(tag: str, reason: str | None = None) -> dict[str, Any]:
    if tag == "Counterexample":
        return {
            "tag": "Counterexample",
            "args": [{"tag": "FreshProtectedReceiptMatcherV2"}],
        }
    if tag == "Unknown":
        assert reason is not None
        return {"tag": "Unknown", "args": [{"reasonClassId": reason}]}
    return {"tag": "Proved"}


def model_expectation(tag: str, reason: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tag": "ModelStatusPrerequisitesV2",
        "expected_model_status": status_matcher(tag, reason),
    }
    if tag == "Counterexample":
        result["final_replay_expectation"] = {
            "tag": "AcceptedBadStateRequiredV2"
        }
    elif tag == "Proved":
        result["completion_expectation"] = {
            "tag": "AllScheduledModelObligationsClosedV2"
        }
    return result


def stage_report(stage: str, completed_check: str) -> dict[str, Any]:
    return {
        "formatId": "SPS-Harness-Stage-Report-v2",
        "fixtureTier": {"tag": "CandidateOnly"},
        "stageId": stage,
        "completedChecks": [completed_check],
        "findings": [],
        "blockers": [],
        "claimable": False,
        "modelStatus": {"tag": "NotComputed"},
    }


def reporting_failure_expectation() -> dict[str, Any]:
    return {
        "tag": "SPS-Harness-ReportingFailureExpectation-v2",
        "expected_run_state": {"tag": "ReportingFailed"},
        "model_status_field_forbidden": True,
    }


def aggregation_rejected_expectation(error_class: str) -> dict[str, Any]:
    return {
        "tag": "SPS-Harness-AggregationInputRejected-v2",
        "errorClass": error_class,
    }


def retirement_expectation() -> dict[str, Any]:
    """The retirement family records an observation, never a model result.

    part5-soundness.tex:210-219 asks for a retirement statistic in the report
    only; it explicitly requires no change to the theorem.  So the expectation
    object here pins `NotComputed` rather than any ModelStatus constructor.
    """

    return {
        "tag": "SPS-Harness-RetirementCoverageObservationV2",
        "model_status_expectation": {"tag": "NotComputed"},
        "coverage_query_expectation": {"tag": "AllFourCoverageQueriesSatisfiedV2"},
        "statistic_expectation": {"tag": "SPS-Harness-Retirement-Statistic-v2"},
    }


EXPECTED: dict[str, tuple[str, dict[str, Any]]] = {
    "DEF-01": ("definedness", model_expectation("Counterexample")),
    "DEF-02": ("definedness", model_expectation("Unknown", "PossibleUB")),
    "DEF-03": ("definedness", model_expectation("Unknown", "PoisonSemanticsUnsupported")),
    "DEF-04": ("definedness", model_expectation("Unknown", "UninitializedLoadProducesUndef")),
    "REL-01": (
        "release-marker",
        stage_report(
            "ReleaseCarrierValidationV2", "InvalidCallableCarrierShapeCheckedV2"
        ),
    ),
    **{
        f"REL-{index:02d}": (
            "release-marker",
            model_expectation("Unknown", "ReleaseCarrierMismatch"),
        )
        for index in range(2, 15)
    },
    **{
        f"REL-{index:02d}": ("release-marker", model_expectation("Counterexample"))
        for index in range(15, 21)
    },
    "REL-21": (
        "release-marker",
        stage_report(
            "ReleaseCarrierValidationV2", "InvalidCallableCarrierOrdinalShapeCheckedV2"
        ),
    ),
    "OUT-01": ("output-closure", model_expectation("Counterexample")),
    "OUT-02": ("output-closure", model_expectation("Proved")),
    "OUT-03": ("output-closure", model_expectation("Counterexample")),
    "OUT-04": ("output-closure", model_expectation("Unknown", "OutputBindingIncomplete")),
    "OUT-05": ("output-closure", model_expectation("Unknown", "OutputBindingOverlap")),
    "OUT-06": ("output-closure", model_expectation("Unknown", "UninitializedOutputByte")),
    "OUT-07": ("output-closure", model_expectation("Counterexample")),
    "AGG-01": ("aggregation", model_expectation("Counterexample")),
    "AGG-02": ("aggregation", model_expectation("Unknown", "SolverTimeout")),
    "AGG-03": ("aggregation", model_expectation("Unknown", "OpenModelObligations")),
    "AGG-04": ("aggregation", model_expectation("Proved")),
    "AGG-05": (
        "aggregation",
        model_expectation("Unknown", "PONFFPArithmeticUnsupported"),
    ),
    "AGG-06": ("aggregation", model_expectation("Unknown", "VacuousAdmission")),
    "AGG-07": ("aggregation", model_expectation("Unknown", "ExpectedHighVariationAbsent")),
    "AGG-08": (
        "aggregation",
        aggregation_rejected_expectation(
            sps_aggregation.ACCEPTED_REPLAY_INVALIDATING_ERROR
        ),
    ),
    "AGG-09": ("aggregation", reporting_failure_expectation()),
    "AGG-10": (
        "aggregation",
        model_expectation("Unknown", "OpenModelObligations"),
    ),
    "AGG-11": ("aggregation", model_expectation("Counterexample")),
    "AGG-12": (
        "aggregation",
        model_expectation("Unknown", "DiagnosticHealthFailure"),
    ),
    "AGG-13": (
        "aggregation",
        model_expectation("Unknown", "ToolInconsistency"),
    ),
    "AGG-14": (
        "aggregation",
        aggregation_rejected_expectation(
            sps_aggregation.ACCEPTED_REPLAY_INVALIDATING_ERROR
        ),
    ),
    "AGG-15": ("aggregation", model_expectation("Proved")),
    "EXT-01": (
        "external-contract",
        stage_report(
            "MechanismContractValidationV2", "MechanismContractShapeCheckedV2"
        ),
    ),
    "EXT-02": ("external-contract", model_expectation("Unknown", "MechanismNondeterminismUnsupported")),
    "EXT-03": ("external-contract", model_expectation("Unknown", "MechanismNondeterminismUnsupported")),
    "EXT-04": ("external-contract", model_expectation("Unknown", "ContractAllocationUnsupported")),
    "EXT-05": ("external-contract", model_expectation("Counterexample")),
    "EXT-06": ("external-contract", model_expectation("Proved")),
    "MEM-01": ("exact-memory", model_expectation("Proved")),
    "MEM-02": ("exact-memory", model_expectation("Unknown", "UninitializedOutputByte")),
    "MEM-03": ("exact-memory", model_expectation("Unknown", "UninitializedLoadProducesUndef")),
    "MEM-04": ("exact-memory", model_expectation("Proved")),
    "MEM-05": ("exact-memory", model_expectation("Proved")),
    "MEM-06": ("exact-memory", model_expectation("Unknown", "UninitializedOutputByte")),
    "MEM-07": ("exact-memory", model_expectation("Proved")),
    "FRZ-01": ("artifact-freeze", model_expectation("Unknown", "PipelineMismatch")),
    "FRZ-02": (
        "artifact-freeze",
        stage_report("NormalFormNormalizationV2", "SafeFreezeErasureShapeCheckedV2"),
    ),
    "FRZ-03": ("artifact-freeze", model_expectation("Unknown", "FreezeMayChoose")),
    "FRZ-04": ("artifact-freeze", model_expectation("Unknown", "UnsupportedStackProtector")),
    "PTR-01": (
        "pointer-layout",
        stage_report(
            "PointerComparisonValidationV2", "SameRootPointerShapeCheckedV2"
        ),
    ),
    "PTR-02": ("pointer-layout", model_expectation("Unknown", "LayoutDependentPointerComparison")),
    "PTR-03": ("pointer-layout", model_expectation("Unknown", "LayoutDependentPointerComparison")),
    "PTR-04": (
        "pointer-layout",
        stage_report(
            "PointerComparisonValidationV2", "OutsideLifetimePointerShapeCheckedV2"
        ),
    ),
    "ACT-01": ("actor-policy", model_expectation("Counterexample")),
    "ACT-02": ("actor-policy", model_expectation("Counterexample")),
    "ACT-03": ("actor-policy", model_expectation("Counterexample")),
    "ACT-04": ("actor-policy", model_expectation("Unknown", "PlacementMismatch")),
    "ACT-05": ("actor-policy", model_expectation("Proved")),
    "RET-01": ("retirement-coverage", retirement_expectation()),
    "RET-02": ("retirement-coverage", retirement_expectation()),
}

FAMILY_ORDER = (
    "definedness",
    "release-marker",
    "output-closure",
    "aggregation",
    "external-contract",
    "exact-memory",
    "artifact-freeze",
    "pointer-layout",
    "actor-policy",
    "retirement-coverage",
)

MARKER_A = (
    "__sps_invalid_callable_emit_"
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
)

STRUCTURAL_RELEASE_MUTATIONS = {
    "REL-02": "missing-marker",
    "REL-03": "duplicate-marker",
    "REL-04": "wrong-symbol",
    "REL-05": "wrong-type",
    "REL-06": "tail-call",
    "REL-07": "varargs",
    "REL-08": "operand-bundle",
    "REL-09": "wrong-calling-convention",
    "REL-10": "missing-noinline",
    "REL-11": "missing-nooutline",
    "REL-12": "missing-noduplicate",
    "REL-13": "missing-nomerge",
    "REL-14": "missing-nobuiltin",
}

SEMANTIC_RELEASE_MUTATIONS = {
    "REL-15": "wrong-value",
    "REL-16": "binding-guard-negated",
    "REL-17": "binding-footprint-mismatch",
    "REL-18": "binding-site-mismatch",
    "REL-19": "binding-ordinal-mismatch",
    "REL-20": "binding-count-mismatch",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def resolve_under(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        fail(f"path escapes harness root: {relative}")
    if not path.is_file():
        fail(f"missing fixture input: {relative}")
    return path


def function_definition(text: str, symbol: str) -> tuple[str, str]:
    match = re.search(
        rf"^(?P<header>define\b[^\n]*@{re.escape(symbol)}\([^{{\n]*\)[^{{\n]*)\{{"
        rf"(?P<body>.*?)^\}}",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        fail(f"missing LLVM function: {symbol}")
    return match.group("header"), match.group("body")


def require(body: str, fragment: str, case_id: str) -> None:
    if fragment not in body:
        fail(f"{case_id}: missing decisive LLVM fragment: {fragment}")


def attribute_groups(text: str) -> dict[int, set[str]]:
    groups: dict[int, set[str]] = {}
    for number, body in re.findall(
        r'^attributes #(\d+) = \{([^}]*)\}$', text, flags=re.MULTILINE
    ):
        groups[int(number)] = set(re.findall(r'"[^"]+"|\S+', body.strip()))
    return groups


def header_attribute_group(header: str, case_id: str) -> int:
    match = re.search(r"#(\d+)\s*$", header)
    if not match:
        fail(f"{case_id}: wrapper has no attribute group")
    return int(match.group(1))


def check_definedness(cases: list[dict[str, Any]], text: str) -> None:
    bodies = {case["id"]: function_definition(text, case["function"])[1] for case in cases}
    require(bodies["DEF-01"], "select i1 %secret, i32 0, i32 1", "DEF-01")
    require(bodies["DEF-01"], "udiv i32 %x, %divisor", "DEF-01")
    require(bodies["DEF-02"], "udiv i32 %x, 0", "DEF-02")
    require(bodies["DEF-03"], "select i1 %secret, i32 32, i32 33", "DEF-03")
    require(bodies["DEF-03"], "shl i32 %x, %amount", "DEF-03")
    require(bodies["DEF-04"], "alloca i8", "DEF-04")
    require(bodies["DEF-04"], "load i8, ptr %slot", "DEF-04")
    if "store " in bodies["DEF-04"]:
        fail("DEF-04: uninitialized-load fixture unexpectedly initializes its slot")
    if cases[3].get("shape_contract", {}).get("ub_risk_forbidden") is not True:
        fail("DEF-04: oracle must distinguish undef from UBRisk")


def check_release_markers(cases: list[dict[str, Any]], text: str) -> None:
    groups = attribute_groups(text)
    exact_pins = {"noinline", '"nooutline"', "noduplicate", "nomerge", "nobuiltin"}
    if groups.get(0) != exact_pins:
        fail("REL-01: conforming wrapper does not have the exact five preservation pins")
    if groups.get(1) != {"nounwind", "willreturn", "memory(none)"}:
        fail("REL-01: marker does not have the exact side-effect-free attributes")

    by_id = {case["id"]: case for case in cases}
    positive_header, positive = function_definition(text, "release_conforming")
    if header_attribute_group(positive_header, "REL-01") != 0:
        fail("REL-01: conforming wrapper is not bound to the exact pin group")
    if positive.count(f"call ccc void @{MARKER_A}(i8 %value) #1") != 1:
        fail("REL-01: conforming wrapper needs exactly one direct ccc marker call")

    expected_marker_counts = {"REL-02": 0, "REL-03": 2}
    for case_id, count in expected_marker_counts.items():
        _, body = function_definition(text, by_id[case_id]["function"])
        if body.count("__sps_invalid_callable_emit_") != count:
            fail(f"{case_id}: wrong marker occurrence count")

    _, wrong_symbol = function_definition(text, "release_wrong_symbol")
    require(wrong_symbol, "__sps_invalid_callable_emit_bbbbb", "REL-04")
    _, wrong_type = function_definition(text, "release_wrong_type")
    require(wrong_type, "call ccc i8 @__sps_invalid_callable_emit_cccccc", "REL-05")
    _, tail = function_definition(text, "release_tail_marker")
    require(tail, "tail call ccc void", "REL-06")
    _, varargs = function_definition(text, "release_varargs_marker")
    require(varargs, "call ccc void (i8, ...)", "REL-07")
    _, bundled = function_definition(text, "release_operand_bundle")
    require(bundled, '[ "sps.test"() ]', "REL-08")
    _, wrong_cc = function_definition(text, "release_wrong_cc")
    require(wrong_cc, "call fastcc void", "REL-09")

    missing_pins = {
        "REL-10": "noinline",
        "REL-11": '"nooutline"',
        "REL-12": "noduplicate",
        "REL-13": "nomerge",
        "REL-14": "nobuiltin",
    }
    for case_id, missing in missing_pins.items():
        case = by_id[case_id]
        header, body = function_definition(text, case["function"])
        actual = groups.get(header_attribute_group(header, case_id))
        if actual != exact_pins - {missing}:
            fail(f"{case_id}: must remove only {missing} from the five-pin set")
        if body.count(f"@{MARKER_A}") != 1:
            fail(f"{case_id}: pin mutation must preserve one marker call")

    _, wrong_value = function_definition(text, "release_wrong_value")
    require(wrong_value, f"@{MARKER_A}(i8 0)", "REL-15")
    _, guarded = function_definition(text, "release_guarded")
    require(guarded, "br i1 %guard, label %emit, label %done", "REL-16")
    require(guarded, f"call ccc void @{MARKER_A}(i8 %value) #1", "REL-16")

    for case_id, mutation in STRUCTURAL_RELEASE_MUTATIONS.items():
        if by_id[case_id].get("mutation") != mutation:
            fail(f"{case_id}: wrong one-property structural mutation")
    for case_id, mutation in SEMANTIC_RELEASE_MUTATIONS.items():
        if by_id[case_id].get("mutation") != mutation:
            fail(f"{case_id}: wrong one-property release-table mutation")

    retry = by_id["REL-21"]
    _, retry_body = function_definition(text, retry["function"])
    false_call = "call ccc void @release_guarded(i8 %value, i1 false)"
    true_call = "call ccc void @release_guarded(i8 %value, i1 true)"
    require(retry_body, false_call, "REL-21")
    require(retry_body, true_call, "REL-21")
    if retry_body.index(false_call) >= retry_body.index(true_call):
        fail("REL-21: guard-false attempt 0 must precede guard-true attempt 1")
    if retry.get("shape_contract") != {"attempt_guards": [False, True], "emitted_ordinal": 1}:
        fail("REL-21: emitted ordinal must remain wrapper-attempt ordinal 1")


def check_output_closure(cases: list[dict[str, Any]], text: str) -> None:
    by_id = {case["id"]: case for case in cases}
    bodies = {case_id: function_definition(text, case["function"])[1] for case_id, case in by_id.items()}
    require(bodies["OUT-01"], "ret i8 %secret", "OUT-01")
    require(bodies["OUT-02"], "ret i8 7", "OUT-02")
    require(bodies["OUT-03"], "store i8 %secret, ptr %output", "OUT-03")
    require(bodies["OUT-04"], "getelementptr i8, ptr %output, i64 1", "OUT-04")
    if by_id["OUT-04"].get("mutation") != "omit-byte-1":
        fail("OUT-04: the output schedule must omit byte 1")
    if by_id["OUT-05"].get("mutation") != "bind-byte-0-twice":
        fail("OUT-05: overlap control must bind byte 0 twice")
    require(bodies["OUT-06"], "store i8 %secret, ptr %output", "OUT-06")
    if "getelementptr" in bodies["OUT-06"]:
        fail("OUT-06: terminal byte 1 must remain uninitialized")
    require(bodies["OUT-07"], "br label %continues", "OUT-07")
    require(bodies["OUT-07"], "ret i8 0", "OUT-07")


def parse_aggregation_input(value: object, case_id: str) -> sps_aggregation.AggregationInputV2:
    try:
        return sps_aggregation.AggregationInputV2.from_json(value)
    except sps_aggregation.AggregationInputError as error:
        fail(f"{case_id}: invalid authoritative AggregationInputV2: {error}")


def aggregation_expectation(
    outcome: sps_aggregation.AggregationOutcomeV2,
) -> dict[str, Any]:
    """Translate a typed result into this catalog's nonclaimable matcher."""

    if isinstance(outcome, sps_aggregation.ReportingFailedAggregationV2):
        return reporting_failure_expectation()

    status = outcome.model_status
    tag = status.get("tag")
    if tag == "Counterexample":
        args = status.get("args")
        if (
            not isinstance(args, list)
            or len(args) != 1
            or not isinstance(args[0], str)
            or not re.fullmatch(r"[0-9a-f]{64}", args[0])
        ):
            fail("accepted replay must produce one protected receipt id")
        return model_expectation("Counterexample")
    if tag == "Proved":
        return model_expectation("Proved")
    if tag == "Unknown":
        args = status.get("args")
        if (
            not isinstance(args, list)
            or len(args) != 1
            or not isinstance(args[0], dict)
            or not isinstance(args[0].get("reasonClassId"), str)
        ):
            fail("typed aggregation produced a malformed Unknown matcher")
        return model_expectation("Unknown", args[0]["reasonClassId"])
    fail(f"typed aggregation produced unsupported ModelStatus matcher {status!r}")


def check_aggregation(cases: list[dict[str, Any]], catalog: object) -> None:
    if (
        not isinstance(catalog, dict)
        or list(catalog) != ["formatId", "authority", "cases"]
        or catalog.get("formatId") != "SPS-Harness-Rev4.1-Aggregation-Inputs-v2"
        or catalog.get("authority")
        != {"tag": "SyntheticInterfaceVectorV2", "claimable": False}
        or not isinstance(catalog.get("cases"), dict)
    ):
        fail("aggregation input catalog has the wrong harness envelope")
    inputs = catalog["cases"]
    expected_ids = [case["id"] for case in cases]
    if list(inputs) != expected_ids:
        fail("aggregation input catalog must cover every AGG case in fixture order")
    for case in cases:
        aggregation_input = parse_aggregation_input(inputs[case["id"]], case["id"])
        try:
            outcome = sps_aggregation.aggregate_model_result(aggregation_input)
        except sps_aggregation.AggregationInputError as error:
            expected = aggregation_rejected_expectation(error.code)
            if expected != case["expectation"]:
                fail(
                    f"{case['id']}: aggregation rejected with {error.code!r}, "
                    f"expected {case['expectation']!r}"
                )
            continue
        public = aggregation_expectation(outcome)
        if public != case["expectation"]:
            fail(
                f"{case['id']}: aggregation prerequisites produced {public!r}, "
                f"expected {case['expectation']!r}"
            )
    fp_unsupported = next(case for case in cases if case["id"] == "AGG-05")
    if fp_unsupported.get("preflight_leak_finding") is not True:
        fail("AGG-05: FP-unsupported apparent leak must remain a preflight finding")
    diagnostic = next(case for case in cases if case["id"] == "AGG-15")
    if diagnostic.get("diagnostic_finding") != "RelationalRequired":
        fail("AGG-15: the non-voting diagnostic finding was not preserved")


def check_external_contract(cases: list[dict[str, Any]], text: str) -> None:
    by_id = {case["id"]: case for case in cases}
    scalar = function_definition(text, "call_contracted_scalar")[1]
    require(scalar, "call i32 @contracted_scalar(i32 %value)", "EXT-01")
    allocate = function_definition(text, "call_contracted_allocate")[1]
    require(allocate, "call ptr @contracted_allocate(i64 %size)", "EXT-04")
    visible = function_definition(text, "visible_host_transfer")[1]
    hidden = function_definition(text, "hidden_host_transfer")[1]
    require(visible, "@sps_host_transfer_i8(i8 %secret, i1 true)", "EXT-05")
    require(hidden, "@sps_host_transfer_i8(i8 %secret, i1 false)", "EXT-06")
    variants = [by_id[f"EXT-{index:02d}"].get("contract_variant") for index in range(1, 5)]
    if variants != [
        "complete-total-single-valued",
        "missing-functional-row",
        "two-unequal-results",
        "returns-fresh-pointer",
    ]:
        fail("external-contract cases do not isolate the four required contract variants")


def check_exact_memory(cases: list[dict[str, Any]], text: str) -> None:
    by_id = {case["id"]: case for case in cases}
    body = lambda case_id: function_definition(text, by_id[case_id]["function"])[1]
    require(body("MEM-01"), "icmp eq i64 %next, 4", "MEM-01")
    require(body("MEM-01"), "store i8 0, ptr %address", "MEM-01")
    require(body("MEM-02"), "br i1 %stop, label %exit, label %continue", "MEM-02")
    memcpy = body("MEM-03")
    require(memcpy, "alloca [2 x i8]", "MEM-03")
    require(memcpy, "@llvm.memcpy.p0.p0.i64", "MEM-03")
    if memcpy.count("store i8") != 1:
        fail("MEM-03: exactly one of the two source bytes must be initialized")
    require(body("MEM-04"), "@llvm.memmove.p0.p0.i64", "MEM-04")
    require(body("MEM-04"), "i64 3", "MEM-04")
    require(body("MEM-05"), "@llvm.memcpy.p0.p0.i64", "MEM-05")
    require(body("MEM-05"), "i64 0", "MEM-05")
    require(body("MEM-06"), "store i8 0, ptr %output", "MEM-06")
    require(body("MEM-07"), "store i32 0, ptr %output", "MEM-07")


def check_artifact_freeze(cases: list[dict[str, Any]], text: str) -> None:
    by_id = {case["id"]: case for case in cases}
    mutation = function_definition(text, by_id["FRZ-01"]["function"])[1]
    require(mutation, "add i32 %value, 0", "FRZ-01")
    header, defined = function_definition(text, by_id["FRZ-02"]["function"])
    require(header, "i32 noundef %value", "FRZ-02")
    require(defined, "freeze i32 %value", "FRZ-02")
    undef = function_definition(text, by_id["FRZ-03"]["function"])[1]
    require(undef, "freeze i32 undef", "FRZ-03")
    header, _ = function_definition(text, by_id["FRZ-04"]["function"])
    require(header, "sspstrong", "FRZ-04")


def check_pointer_layout(cases: list[dict[str, Any]], text: str) -> None:
    by_id = {case["id"]: case for case in cases}
    same = function_definition(text, by_id["PTR-01"]["function"])[1]
    if same.count("getelementptr i8, ptr %root, i64 %offset") != 2:
        fail("PTR-01: both pointer terms must be the same root and offset")
    adjacent = function_definition(text, by_id["PTR-02"]["function"])[1]
    require(adjacent, "getelementptr [4 x i8], ptr %object_a, i64 0, i64 4", "PTR-02")
    require(adjacent, "getelementptr [1 x i8], ptr %object_b, i64 0, i64 0", "PTR-02")
    header, wrapping = function_definition(text, by_id["PTR-03"]["function"])
    require(header, "ptr nonnull %root", "PTR-03")
    require(wrapping, "getelementptr i8, ptr %root, i64 %offset", "PTR-03")
    require(wrapping, "icmp eq ptr %wrapped, null", "PTR-03")
    outside = function_definition(text, by_id["PTR-04"]["function"])[1]
    end_index = outside.index("@llvm.lifetime.end.p0")
    compare_index = outside.index("icmp eq ptr %object, null")
    if end_index >= compare_index or "load " in outside or "store " in outside:
        fail("PTR-04: comparison must follow lifetime.end without dereference")


def check_actor_policy(cases: list[dict[str, Any]], root: Path) -> None:
    required_tokens = {
        "ACT-01": ('minimally_joint_visible = [["alice", "bob"]]', 'sps.audience = ["alice", "bob"]'),
        "ACT-02": ('{item = "embeddings", visible_to = ["alice"]}', '{item = "raw_prompt", visible_to = []}'),
        "ACT-03": ('sps.principals = ["alice", "bob", "carol"]', 'sps.coalitions_maximal = [["alice", "bob", "carol"]]'),
        "ACT-04": ('sps.placement = [{func = "@serve_placed", host = "host_eu"}]', 'llvm.func @serve_unplaced'),
        "ACT-05": ('{func = "@serve_placed", host = "host_eu"}', '{func = "@serve_unplaced", host = "host_eu"}'),
    }
    for case in cases:
        case_id = case["id"]
        path = resolve_under(root, case["source"])
        text = path.read_text()
        if "// RUN: %mlir-opt %s | %FileCheck %s" not in text:
            fail(f"{case_id}: promoted actor fixture lacks an executable RUN line")
        for token in required_tokens[case_id]:
            require(text, token, case_id)
        rows = case.get("audit_all_expectations")
        if not isinstance(rows, list) or not rows:
            fail(f"{case_id}: actor fixture has no AuditAll expectations")
        for row in rows:
            if row.get("query_kind") != {"tag": "AuditAll"}:
                fail(f"{case_id}: actor row is not an AuditAll query matcher")
            if not isinstance(row.get("entry"), str) or not isinstance(
                row.get("coalition"), list
            ):
                fail(f"{case_id}: actor row lacks an entry/coalition scope")
            outcome = row.get("query_outcome_matcher", {})
            if outcome.get("tag") not in {
                "ConstructedResultMatcherV2",
                "NotConstructedResultMatcherV2",
            }:
                fail(f"{case_id}: actor row has an invalid query-outcome matcher")


MASK64 = (1 << 64) - 1

# part5-soundness.tex:198-204 lists the four coverage families of alg:coverage
# in this order, together with the reason each would return if it failed.
REQUIRED_COVERAGE_QUERIES = (
    ("AdmissionNonempty", "VacuousAdmission"),
    ("PairDomainNonempty", "VacuousPairDomain"),
    ("HighVariation", "ExpectedHighVariationAbsent"),
    ("ReleaseActivation", "ReleaseActivationMismatch"),
)


def instruction_steps(body: str) -> list[str]:
    """The entry's instruction sequence, so a step index means something."""

    steps = []
    for raw in body.splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line or re.fullmatch(r"[\w.$-]+:", line):
            continue
        steps.append(line)
    return steps


def released_projection(case_id: str, body: str):
    """Derive the released expression from the entry's own LLVM text.

    Nothing here is hard-coded to the fixture: the shift amounts, the
    multipliers and the mask are read out of the module, so mutating the IR
    moves the statistic computed below.
    """

    shifts = [int(value) for value in re.findall(r"lshr i64 %\w+, (\d+)", body)]
    multipliers = [int(value) for value in re.findall(r"mul i64 %\w+, (-?\d+)", body)]
    masks = [int(value) for value in re.findall(r"%low = and i64 %secret, (-?\d+)", body)]

    if shifts or multipliers:
        if len(shifts) != 3 or len(multipliers) != 2:
            fail(
                f"{case_id}: the finalizer must be exactly three xor-shifts and "
                "two multiplies"
            )
        first, second = (value & MASK64 for value in multipliers)

        def finalizer(secret: int) -> int:
            value = secret ^ (secret >> shifts[0])
            value = (value * first) & MASK64
            value = value ^ (value >> shifts[1])
            value = (value * second) & MASK64
            return value ^ (value >> shifts[2])

        return "splitmix64-finalizer", finalizer

    if len(masks) == 1:
        mask = masks[0] & MASK64
        return "bit-mask", lambda secret: secret & mask

    fail(f"{case_id}: entry has no recognizable released projection")


def retirement_shape(case_id: str, case: dict[str, Any], text: str):
    """Locate the single release and the post-release secret-dependent step."""

    _, body = function_definition(text, case["function"])
    steps = instruction_steps(body)
    wrapper = case["release_wrapper"]
    releases = [
        index
        for index, step in enumerate(steps, 1)
        if step.startswith(f"call ccc void @{wrapper}(")
    ]
    if len(releases) != 1:
        fail(f"{case_id}: entry must contain exactly one authorized release site")
    release_index = releases[0]
    if any(step.startswith("br ") for step in steps[: release_index - 1]):
        fail(
            f"{case_id}: the release must be unconditional so ReleaseActivation "
            "holds on every admitted execution"
        )

    selectors = [
        (index, int(value))
        for index, step in enumerate(steps, 1)
        for value in re.findall(r"^%probe = and i64 %secret, (\d+)$", step)
    ]
    if len(selectors) != 1:
        fail(f"{case_id}: entry must contain exactly one post-release secret selector")
    selector_index, selector_mask = selectors[0]
    if selector_index <= release_index:
        fail(
            f"{case_id}: the secret-dependent difference must come after the "
            "release, otherwise retirement is not what hides it"
        )
    if not any(step.startswith("store i64 ") for step in steps[selector_index:]):
        fail(f"{case_id}: the post-release difference must reach a public store")

    kind, projection = released_projection(case_id, body)
    return {
        "kind": kind,
        "projection": projection,
        "selector_mask": selector_mask,
        "first_release_step_index": release_index,
        "total_steps": len(steps),
    }


def retirement_statistic(case: dict[str, Any], shape: dict[str, Any]) -> dict[str, Any]:
    """The per-(entry, coalition) statistic of part5-soundness.tex:210-219."""

    bits = case["pair_domain_model"]["secret_bits"]
    size = 1 << bits
    values = [shape["projection"](secret) for secret in range(size)]
    mask = shape["selector_mask"]

    retired = 0
    active_varying = 0
    for left in range(size):
        for right in range(size):
            if values[left] != values[right]:
                retired += 1
            elif (left & mask) != (right & mask):
                active_varying += 1

    admitted = size * size
    return {
        "format": "SPS-Harness-Retirement-Statistic-v2",
        "entry": case["function"],
        "coalition": case["coalition"],
        "secret_bits": bits,
        "released_projection": shape["kind"],
        "admitted_pairs": admitted,
        "secret_varying_pairs": admitted - size,
        "retired_pairs": retired,
        "retired_at_first_release": retired,
        "retirement_fraction_ppm": round(retired * 1_000_000 / admitted),
        "post_release_active_pairs": admitted - retired,
        "post_release_active_varying_pairs": active_varying,
        "first_release_step_index": shape["first_release_step_index"],
        "total_steps": shape["total_steps"],
    }


def check_retirement_coverage_queries(
    case_id: str, case: dict[str, Any], derived: dict[str, Any]
) -> None:
    witnessed = {
        "AdmissionNonempty": derived["admitted_pairs"] > 0,
        "PairDomainNonempty": derived["admitted_pairs"] > 0,
        "HighVariation": derived["secret_varying_pairs"] > 0,
        "ReleaseActivation": derived["first_release_step_index"] > 0,
    }
    rows = case.get("coverage_queries")
    if not isinstance(rows, list) or len(rows) != len(REQUIRED_COVERAGE_QUERIES):
        fail(f"{case_id}: all four coverage queries of alg:coverage must be recorded")
    for row, (name, reason) in zip(rows, REQUIRED_COVERAGE_QUERIES):
        if row.get("query") != name:
            fail(f"{case_id}: coverage query rows must stay in the order of alg:coverage")
        if row.get("blocking_reason_if_absent") != reason:
            fail(f"{case_id}: coverage query {name} must name reason {reason}")
        if row.get("harness_observation") != "Satisfied":
            fail(
                f"{case_id}: coverage query {name} must be recorded Satisfied; "
                "part5-soundness.tex:195-208 is the claim that every one of the "
                "four passes and none of them sees the collapse"
            )
        if not witnessed[name]:
            fail(
                f"{case_id}: coverage query {name} is recorded Satisfied but the "
                "enumerated pair-domain model does not witness it"
            )


def check_retirement_coverage(cases: list[dict[str, Any]], text: str) -> list[str]:
    by_id = {case["id"]: case for case in cases}
    if set(by_id) != {"RET-01", "RET-02"}:
        fail("retirement-coverage needs exactly the collapsing case and its contrast")

    report: list[str] = []
    derived_by_id: dict[str, dict[str, Any]] = {}
    shapes: dict[str, dict[str, Any]] = {}
    for case_id in ("RET-01", "RET-02"):
        case = by_id[case_id]
        shape = shapes[case_id] = retirement_shape(case_id, case, text)
        derived = derived_by_id[case_id] = retirement_statistic(case, shape)

        recorded = case.get("retirement_statistic")
        if not isinstance(recorded, dict) or set(recorded) != set(derived):
            fail(f"{case_id}: retirement statistic fields do not match the derived record")
        for key, value in derived.items():
            if recorded[key] != value:
                fail(
                    f"{case_id}: recomputed retirement statistic disagrees on {key}: "
                    f"derived {value!r}, recorded {recorded[key]!r}"
                )

        check_retirement_coverage_queries(case_id, case, derived)

        note = case.get("vacuous_proved_note", "")
        for fragment in ("vacuous-by-retirement", "does not compute a ModelStatus"):
            if fragment not in note:
                fail(f"{case_id}: the vacuity note must say {fragment!r}")
        scanned = {key: value for key, value in case.items() if key != "vacuous_proved_note"}
        if "Proved" in json.dumps(scanned):
            fail(
                f"{case_id}: retirement fixtures must not carry a Proved ModelStatus "
                "claim; a Proved on the collapsing side would be vacuous-by-retirement"
            )

        report.append(
            "SPS-Harness-Retirement-Statistic-v2 "
            f"entry={derived['entry']} coalition=[{','.join(derived['coalition'])}] "
            f"projection={derived['released_projection']} "
            f"admitted_pairs={derived['admitted_pairs']} "
            f"retired_pairs={derived['retired_pairs']} "
            f"retirement_ppm={derived['retirement_fraction_ppm']} "
            f"first_release_step={derived['first_release_step_index']}"
            f"/{derived['total_steps']} "
            f"post_release_active_pairs={derived['post_release_active_pairs']} "
            f"post_release_active_varying_pairs="
            f"{derived['post_release_active_varying_pairs']}"
        )

    if shapes["RET-01"]["selector_mask"] != shapes["RET-02"]["selector_mask"]:
        fail(
            "retirement-coverage: both entries must diverge on the same secret bit, "
            "otherwise the contrast measures the tail rather than the release"
        )

    collapsing = derived_by_id["RET-01"]
    if collapsing["retirement_fraction_ppm"] < 990_000:
        fail(
            "RET-01: an injective release must collapse coverage; derived "
            f"retirement_fraction_ppm={collapsing['retirement_fraction_ppm']}"
        )
    if collapsing["post_release_active_varying_pairs"] != 0:
        fail(
            "RET-01: an injective release must leave no secret-varying pair active "
            "after the release"
        )

    contrast = derived_by_id["RET-02"]
    if contrast["post_release_active_varying_pairs"] == 0:
        fail(
            "RET-02: the contrast entry must keep the post-release secret-dependent "
            "difference in scope; derived post_release_active_varying_pairs=0"
        )
    if contrast["retirement_fraction_ppm"] > 750_000:
        fail(
            "RET-02: the contrast release must retire only part of the pair domain; "
            f"derived retirement_fraction_ppm={contrast['retirement_fraction_ppm']}"
        )

    report.append(
        "SPS-Harness-Retirement-Coverage-Note-v2 "
        "all-four-coverage-queries=Satisfied "
        "collapsing-entry=release_injective_digest "
        "contrast-entry=release_low_bit "
        "model_status=NotComputed nf_conforms=NotEvaluated"
    )
    return report


def check_case_inventory(cases: Any) -> list[dict[str, Any]]:
    if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases):
        fail("cases must be a list of objects")
    ids = tuple(case.get("id") for case in cases)
    if ids != tuple(EXPECTED):
        fail(
            "case inventory, order, or uniqueness does not match the "
            f"{len(EXPECTED)} required fixtures"
        )
    for case in cases:
        case_id = case["id"]
        family, expectation = EXPECTED[case_id]
        if case.get("family") != family or case.get("expectation") != expectation:
            fail(f"{case_id}: wrong family or expected Rev4 prerequisite")
        if expectation.get("formatId") == check_sps_stage_report.FORMAT_ID:
            try:
                check_sps_stage_report.validate_stage_report(
                    expectation, source=f"{case_id}.expectation"
                )
            except check_sps_stage_report.StageReportError as error:
                fail(str(error))
        if not isinstance(case.get("title"), str) or not case["title"]:
            fail(f"{case_id}: missing review title")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--family", choices=FAMILY_ORDER)
    args = parser.parse_args()

    root = args.root.resolve()
    catalog_path = root / "integration" / "Inputs" / "sps-rev4-high-value" / "cases.json"
    catalog = json.loads(catalog_path.read_text())
    if catalog.get("schema_version") != "SPS-Harness-Rev4-High-Value-Fixtures-v3":
        fail("unsupported high-value fixture schema")
    authority = catalog.get("authority")
    if authority != {
        "tier": {"tag": "CandidateOnly"},
        "claimable": False,
        "checker_status": "Unimplemented",
        "current_status": "Pending",
        "statement": (
            "Expectations are harness-scoped prerequisites and stage reports; "
            "no SPS run report or ModelStatus has been computed."
        ),
    }:
        fail("suite authority must remain exactly nonclaimable and Pending")

    inputs = catalog.get("inputs")
    if not isinstance(inputs, dict) or tuple(inputs) != FAMILY_ORDER:
        fail("fixture input map does not cover all families in normative review order")
    texts: dict[str, str] = {}
    for family, relative in inputs.items():
        if relative is not None:
            texts[family] = resolve_under(root, relative).read_text()

    cases = check_case_inventory(catalog.get("cases"))
    grouped = {family: [case for case in cases if case["family"] == family] for family in FAMILY_ORDER}

    check_definedness(grouped["definedness"], texts["definedness"])
    check_release_markers(grouped["release-marker"], texts["release-marker"])
    check_output_closure(grouped["output-closure"], texts["output-closure"])
    check_aggregation(grouped["aggregation"], json.loads(texts["aggregation"]))
    check_external_contract(grouped["external-contract"], texts["external-contract"])
    check_exact_memory(grouped["exact-memory"], texts["exact-memory"])
    check_artifact_freeze(grouped["artifact-freeze"], texts["artifact-freeze"])
    check_pointer_layout(grouped["pointer-layout"], texts["pointer-layout"])
    check_actor_policy(grouped["actor-policy"], root)
    retirement_report = check_retirement_coverage(
        grouped["retirement-coverage"], texts["retirement-coverage"]
    )

    selected = (args.family,) if args.family else FAMILY_ORDER
    for family in selected:
        print(
            f"verified {family}: {len(grouped[family])} nonclaimable fixture cases; "
            "temporary-bitcode-ready; ModelStatus=not-computed"
        )
    if args.family in (None, "retirement-coverage"):
        for line in retirement_report:
            print(line)
    if args.family is None:
        print(f"verified high-value suite: {len(cases)} cases across {len(FAMILY_ORDER)} families")


if __name__ == "__main__":
    main()
