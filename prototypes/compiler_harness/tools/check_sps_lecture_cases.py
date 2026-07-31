#!/usr/bin/env python3
"""Validate the nonclaimable SPS lecture fixture contracts and LLVM shapes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CASE_IDS = (
    "01-secret-branch",
    "02-branchless-repair",
    "03-missing-placement",
    "04-authorized-release-first",
    "05-branch-before-release",
    "06-equal-release-stays-active",
    "07-wrong-audience-stays-active",
)

EXPECTED = {
    "01-secret-branch": (
        "Counterexample",
        None,
        ("CounterexampleCandidate", "CounterexampleCandidate", "SafeCandidate"),
    ),
    "02-branchless-repair": (
        "Proved",
        None,
        ("SafeCandidate", "SafeCandidate", "SafeCandidate"),
    ),
    "03-missing-placement": (
        "Unknown",
        "PlacementMismatch",
        (
            "Blocked(PlacementMismatch)",
            "Blocked(PlacementMismatch)",
            "Blocked(PlacementMismatch)",
        ),
    ),
    "04-authorized-release-first": (
        "Proved",
        None,
        ("SafeCandidate", "SafeCandidate", "SafeCandidate"),
    ),
    "05-branch-before-release": (
        "Counterexample",
        None,
        ("CounterexampleCandidate", "CounterexampleCandidate", "SafeCandidate"),
    ),
    "06-equal-release-stays-active": (
        "Counterexample",
        None,
        ("CounterexampleCandidate", "CounterexampleCandidate", "SafeCandidate"),
    ),
    "07-wrong-audience-stays-active": (
        "Counterexample",
        None,
        ("CounterexampleCandidate", "CounterexampleCandidate", "SafeCandidate"),
    ),
}

COALITIONS = ([], ["observer"], ["owner"])
WRAPPER_BY_CASE = {
    "04-authorized-release-first": "release_secret",
    "05-branch-before-release": "release_secret",
    "06-equal-release-stays-active": "release_bit",
    "07-wrong-audience-stays-active": "release_secret",
}
EXPECTED_POLICY_REVIEW = {
    "01-secret-branch": "Complete",
    "02-branchless-repair": "Complete",
    "03-missing-placement": "GeneratedLater",
    "04-authorized-release-first": "Findings(IdentityReleaseOfHigh)",
    "05-branch-before-release": "Findings(IdentityReleaseOfHigh)",
    "06-equal-release-stays-active": "Complete",
    "07-wrong-audience-stays-active": "Complete",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def function_body(text: str, symbol: str) -> str:
    match = re.search(
        rf"^define\b[^\n]*@{re.escape(symbol)}\([^{{]*\)\s*(?:#[0-9]+)?\s*\{{"
        rf"(?P<body>.*?)^\}}",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        fail(f"missing function body: {symbol}")
    return match.group("body")


def check_shape(case: dict[str, object], root: Path) -> None:
    case_id = str(case["case_id"])
    relative = Path(str(case["capture_shape"]))
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        fail(f"{case_id}: capture path escapes harness root")
    if not path.is_file():
        fail(f"{case_id}: missing capture shape: {relative}")

    text = path.read_text()
    if re.search(r"^\s*@.*\bglobal\b", text, flags=re.MULTILINE):
        fail(f"{case_id}: mutable/global storage is forbidden in teaching shapes")
    for forbidden in ("%ordinal", "@private_state", "@published"):
        if forbidden in text:
            fail(f"{case_id}: obsolete capture fragment present: {forbidden}")
    if "define i8 @fixture_entry(i8 %secret)" not in text or "ret i8 " not in text:
        fail(f"{case_id}: expected private i8 return entry shape")

    entry = function_body(text, "fixture_entry")
    marker = case["shape_contract"]["marker_symbol"]
    if marker is None:
        if "__sps_release_emit_v1_" in text:
            fail(f"{case_id}: unexpected release marker")
        if case_id == "01-secret-branch" and "br i1 " not in entry:
            fail(f"{case_id}: missing secret-dependent branch")
        if case_id in {"02-branchless-repair", "03-missing-placement"}:
            if "br i1 " in entry or " select " not in entry:
                fail(f"{case_id}: expected branchless select shape")
        return

    marker = str(marker)
    wrapper = WRAPPER_BY_CASE[case_id]
    wrapper_body = function_body(text, wrapper)
    if text.count(f"@{marker}") != 2:
        fail(f"{case_id}: marker must have one declaration and one call")
    if f"call ccc void @{marker}" not in wrapper_body:
        fail(f"{case_id}: marker is not a direct ccc call inside its wrapper")
    if 'attributes #0 = { noinline noduplicate nomerge nobuiltin "nooutline" }' not in text:
        fail(f"{case_id}: wrapper Class-B attribute set is incomplete")
    if "attributes #1 = { nounwind willreturn memory(none) }" not in text:
        fail(f"{case_id}: marker attribute set is not exact")
    wrapper_call = f"call ccc void @{wrapper}"
    if entry.count(wrapper_call) != 1:
        fail(f"{case_id}: entry must contain one direct ccc wrapper call")

    call_index = entry.index(wrapper_call)
    branch_index = entry.index("br i1 ")
    ordering = str(case["shape_contract"]["ordering"])
    if ordering == "branch-before-release" and not branch_index < call_index:
        fail(f"{case_id}: release moved before the leaking branch")
    if ordering != "branch-before-release" and not call_index < branch_index:
        fail(f"{case_id}: release must precede the selected later branch")


def check_case(case: dict[str, object], root: Path) -> None:
    case_id = str(case.get("case_id"))
    if case.get("claimable") is not False or case.get("current_status") != "Pending":
        fail(f"{case_id}: fixture must remain nonclaimable and Pending")
    model_class, reason, rows = EXPECTED[case_id]
    if case.get("expected_model_status_class") != model_class:
        fail(f"{case_id}: wrong expected model-status class")
    if case.get("expected_reason") != reason:
        fail(f"{case_id}: wrong expected reason")
    if case.get("expected_deployment_status") != "Open(P4EvidenceProfileUnavailable)":
        fail(f"{case_id}: wrong base-profile deployment status")
    if case.get("expected_policy_review_status") != EXPECTED_POLICY_REVIEW[case_id]:
        fail(f"{case_id}: wrong expected policy-review status")

    actual_rows = case.get("coalition_rows")
    if not isinstance(actual_rows, list) or len(actual_rows) != 3:
        fail(f"{case_id}: expected exactly three coalition rows")
    for actual, coalition, expected in zip(actual_rows, COALITIONS, rows, strict=True):
        if actual != {"coalition": coalition, "expected": expected}:
            fail(f"{case_id}: wrong or reordered coalition row: {actual!r}")
    check_shape(case, root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case", choices=CASE_IDS)
    args = parser.parse_args()
    root = args.root.resolve()
    inventory_path = root / "integration" / "Inputs" / "sps-lecture" / "cases.json"
    inventory = json.loads(inventory_path.read_text())
    if inventory.get("schema_version") != "sps-lecture-fixture-contracts-v1":
        fail("unsupported SPS lecture fixture schema")
    authority = inventory.get("authority")
    if not isinstance(authority, dict) or authority.get("claimable") is not False:
        fail("suite authority must be explicitly nonclaimable")
    if authority.get("checker_status") != "Unimplemented":
        fail("suite must not imply that the SPS checker exists")

    cases = inventory.get("cases")
    if not isinstance(cases, list):
        fail("cases must be a list")
    by_id = {case.get("case_id"): case for case in cases if isinstance(case, dict)}
    if tuple(by_id) != CASE_IDS or len(by_id) != len(cases):
        fail("case inventory or order does not match the seven lecture cases")

    for case in cases:
        check_case(case, root)

    selected = (by_id[args.case],) if args.case else tuple(cases)
    for case in selected:
        model_class = str(case["expected_model_status_class"])
        reason = case["expected_reason"]
        expected = f"{model_class}({reason})" if reason else model_class
        print(
            f"verified {case['case_id']}: fixture-contract only; "
            f"claimable=false; ModelStatus=not-computed; expected={expected}"
        )


if __name__ == "__main__":
    main()
