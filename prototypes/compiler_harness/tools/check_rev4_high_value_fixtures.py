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


EXPECTED: dict[str, tuple[str, str]] = {
    "DEF-01": ("definedness", "Counterexample(ReplayableWitness)"),
    "DEF-02": ("definedness", "Unknown(PossibleUB)"),
    "DEF-03": ("definedness", "Unknown(PoisonSemanticsUnsupported)"),
    "DEF-04": ("definedness", "Unknown(UninitializedLoadProducesUndef)"),
    "REL-01": ("release-marker", "CarrierAccepted"),
    "REL-02": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-03": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-04": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-05": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-06": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-07": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-08": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-09": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-10": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-11": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-12": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-13": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-14": ("release-marker", "Unknown(ReleaseConformanceMismatch)"),
    "REL-15": ("release-marker", "Counterexample(ReplayableWitness)"),
    "REL-16": ("release-marker", "Counterexample(ReplayableWitness)"),
    "REL-17": ("release-marker", "Counterexample(ReplayableWitness)"),
    "REL-18": ("release-marker", "Counterexample(ReplayableWitness)"),
    "REL-19": ("release-marker", "Counterexample(ReplayableWitness)"),
    "REL-20": ("release-marker", "Counterexample(ReplayableWitness)"),
    "REL-21": ("release-marker", "CarrierAccepted"),
    "OUT-01": ("output-closure", "Counterexample(ReplayableWitness)"),
    "OUT-02": ("output-closure", "Proved"),
    "OUT-03": ("output-closure", "Counterexample(ReplayableWitness)"),
    "OUT-04": ("output-closure", "Unknown(OutputBindingIncomplete)"),
    "OUT-05": ("output-closure", "Unknown(OutputBindingOverlap)"),
    "OUT-06": ("output-closure", "Unknown(UninitializedOutputByte)"),
    "OUT-07": ("output-closure", "Counterexample(ReplayableWitness)"),
    "AGG-01": ("aggregation", "Counterexample(ReplayableWitness)"),
    "AGG-02": ("aggregation", "Unknown(SolverTimeout)"),
    "AGG-03": ("aggregation", "Unknown(OpenModelObligations)"),
    "AGG-04": ("aggregation", "Proved"),
    "AGG-05": ("aggregation", "Unknown(PipelineMismatch)"),
    "AGG-06": ("aggregation", "Unknown(VacuousAdmission)"),
    "AGG-07": ("aggregation", "Unknown(ExpectedHighVariationAbsent)"),
    "EXT-01": ("external-contract", "ContractAccepted"),
    "EXT-02": (
        "external-contract",
        "Unknown(MechanismNondeterminismUnsupported)",
    ),
    "EXT-03": (
        "external-contract",
        "Unknown(MechanismNondeterminismUnsupported)",
    ),
    "EXT-04": ("external-contract", "Unknown(ContractAllocationUnsupported)"),
    "EXT-05": ("external-contract", "Counterexample(ReplayableWitness)"),
    "EXT-06": ("external-contract", "Proved"),
    "MEM-01": ("exact-memory", "Proved"),
    "MEM-02": ("exact-memory", "Unknown(UninitializedOutputByte)"),
    "MEM-03": ("exact-memory", "Unknown(UninitializedLoadProducesUndef)"),
    "MEM-04": ("exact-memory", "Proved"),
    "MEM-05": ("exact-memory", "Proved"),
    "MEM-06": ("exact-memory", "Unknown(UninitializedOutputByte)"),
    "MEM-07": ("exact-memory", "Proved"),
    "FRZ-01": ("artifact-freeze", "Unknown(PipelineMismatch)"),
    "FRZ-02": ("artifact-freeze", "NormalizerAccepted"),
    "FRZ-03": ("artifact-freeze", "Unknown(FreezeMayChoose)"),
    "FRZ-04": ("artifact-freeze", "Unknown(UnsupportedStackProtector)"),
    "PTR-01": ("pointer-layout", "ComparisonAccepted"),
    "PTR-02": ("pointer-layout", "Unknown(LayoutDependentPointerComparison)"),
    "PTR-03": ("pointer-layout", "Unknown(LayoutDependentPointerComparison)"),
    "PTR-04": ("pointer-layout", "ComparisonAccepted"),
    "ACT-01": ("actor-policy", "Counterexample(ReplayableWitness)"),
    "ACT-02": ("actor-policy", "Counterexample(ReplayableWitness)"),
    "ACT-03": ("actor-policy", "Counterexample(ReplayableWitness)"),
    "ACT-04": ("actor-policy", "Unknown(ManifestMismatch)"),
    "ACT-05": ("actor-policy", "Proved"),
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
)

MARKER_A = (
    "__sps_release_emit_v1_"
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
    if cases[3].get("oracle", {}).get("ub_risk_forbidden") is not True:
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
        if body.count("__sps_release_emit_v1_") != count:
            fail(f"{case_id}: wrong marker occurrence count")

    _, wrong_symbol = function_definition(text, "release_wrong_symbol")
    require(wrong_symbol, "__sps_release_emit_v1_bbbbb", "REL-04")
    _, wrong_type = function_definition(text, "release_wrong_type")
    require(wrong_type, "call ccc i8 @__sps_release_emit_v1_cccccc", "REL-05")
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
    if retry.get("oracle") != {"attempt_guards": [False, True], "emitted_ordinal": 1}:
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


def aggregate(inputs: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    """Small executable statement of the strict artifact-level priority rule."""

    if inputs.get("conformant") is not True:
        return "Unknown(PipelineMismatch)", ("PipelineMismatch",)

    blockers = tuple(str(reason) for reason in inputs.get("blockers", ()))
    if inputs.get("replayed_counterexample") is True:
        return "Counterexample(ReplayableWitness)", blockers
    if len(blockers) == 1:
        return f"Unknown({blockers[0]})", blockers
    if len(blockers) > 1:
        return "Unknown(OpenModelObligations)", blockers
    return "Proved", ()


def check_aggregation(cases: list[dict[str, Any]]) -> None:
    for case in cases:
        public, private = aggregate(case.get("inputs", {}))
        if public != case["expected"]:
            fail(f"{case['id']}: aggregation produced {public}, expected {case['expected']}")
        if list(private) != case.get("private_reasons"):
            fail(f"{case['id']}: private blocker ledger was not preserved exactly")
    nonconformant = next(case for case in cases if case["id"] == "AGG-05")
    if nonconformant["inputs"].get("preflight_leak_finding") is not True:
        fail("AGG-05: nonconformant apparent leak must remain an explicit preflight finding")


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
        compact = re.sub(r"\s+", "", text)
        rows = case.get("rows")
        if not isinstance(rows, list) or not rows:
            fail(f"{case_id}: actor fixture has no expected product rows")
        for coordinate, disposition in rows:
            needle = coordinate.replace("/", "") + disposition
            if needle not in compact:
                fail(f"{case_id}: source comment lacks product row {coordinate} {disposition}")


def check_case_inventory(cases: Any) -> list[dict[str, Any]]:
    if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases):
        fail("cases must be a list of objects")
    ids = tuple(case.get("id") for case in cases)
    if ids != tuple(EXPECTED):
        fail("case inventory, order, or uniqueness does not match the 65 required fixtures")
    for case in cases:
        case_id = case["id"]
        family, expected = EXPECTED[case_id]
        if case.get("family") != family or case.get("expected") != expected:
            fail(f"{case_id}: wrong family or expected disposition")
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
    if catalog.get("schema_version") != "sps-rev4-high-value-fixtures-v1":
        fail("unsupported high-value fixture schema")
    authority = catalog.get("authority")
    if authority != {
        "claimable": False,
        "checker_status": "Unimplemented",
        "current_status": "Pending",
        "statement": "Expected dispositions are hand-authored Rev. 4 fixture oracles, not current verifier results.",
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
    check_aggregation(grouped["aggregation"])
    check_external_contract(grouped["external-contract"], texts["external-contract"])
    check_exact_memory(grouped["exact-memory"], texts["exact-memory"])
    check_artifact_freeze(grouped["artifact-freeze"], texts["artifact-freeze"])
    check_pointer_layout(grouped["pointer-layout"], texts["pointer-layout"])
    check_actor_policy(grouped["actor-policy"], root)

    selected = (args.family,) if args.family else FAMILY_ORDER
    for family in selected:
        print(
            f"verified {family}: {len(grouped[family])} nonclaimable fixture cases; "
            "temporary-bitcode-ready; ModelStatus=not-computed"
        )
    if args.family is None:
        print(f"verified high-value suite: {len(cases)} cases across {len(FAMILY_ORDER)} families")


if __name__ == "__main__":
    main()
