#!/usr/bin/env python3
"""Validate the nonclaimable SPS lecture fixture contracts and LLVM shapes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


SOURCE_ROOT_ENV = "SPS_LECTURE_SOURCE"
SOURCE_BINDING_FORMAT_ID = "SPS-Harness-Lecture-Source-Binding-v1"
SOURCE_RELATIVE_NAME = "frozen.ll.sketch"

CASE_IDS = (
    "01-secret-branch",
    "02-branchless-repair",
    "03-missing-placement",
    "04-authorized-release-first",
    "05-branch-before-release",
    "06-equal-release-stays-active",
    "07-wrong-audience-stays-active",
)

COALITIONS = ([], ["observer"], ["owner"])


def status_matcher(tag: str, reason: str | None = None) -> dict[str, object]:
    if tag == "Counterexample":
        return {
            "tag": "Counterexample",
            "args": [{"tag": "FreshProtectedReceiptMatcherV1"}],
        }
    if tag == "Unknown":
        assert reason is not None
        return {"tag": "Unknown", "args": [{"reasonClassId": reason}]}
    return {"tag": "Proved"}


def audit_expectation(
    coalition: list[str], raw_result: str | None, reason: str | None = None
) -> dict[str, object]:
    row: dict[str, object] = {
        "query_kind": {"tag": "AuditAll"},
        "entry": "fixture_entry",
        "coalition": coalition,
    }
    if raw_result is None:
        assert reason is not None
        row["query_outcome_matcher"] = {
            "tag": "NotConstructedResultMatcherV1",
            "reason": {"reasonClassId": reason},
        }
        row["final_replay_expectation"] = {
            "tag": "NotAvailableV1",
            "reason": {"reasonClassId": reason},
        }
        return row
    candidate = raw_result == "SAT"
    row["query_outcome_matcher"] = {
        "tag": "ConstructedResultMatcherV1",
        "raw_solver_result": raw_result,
        "query_disposition": {"tag": "CandidateOnly" if candidate else "Discharged"},
    }
    row["final_replay_expectation"] = {
        "tag": "AcceptedBadStateRequiredV1" if candidate else "NotApplicableV1"
    }
    return row


SAFE_ROWS = tuple(audit_expectation(coalition, "UNSAT") for coalition in COALITIONS)
BAD_ROWS = (
    audit_expectation(COALITIONS[0], "SAT"),
    audit_expectation(COALITIONS[1], "SAT"),
    audit_expectation(COALITIONS[2], "UNSAT"),
)
PLACEMENT_ROWS = tuple(
    audit_expectation(coalition, None, "PlacementMismatch")
    for coalition in COALITIONS
)

EXPECTED = {
    "01-secret-branch": (status_matcher("Counterexample"), BAD_ROWS),
    "02-branchless-repair": (status_matcher("Proved"), SAFE_ROWS),
    "03-missing-placement": (
        status_matcher("Unknown", "PlacementMismatch"),
        PLACEMENT_ROWS,
    ),
    "04-authorized-release-first": (status_matcher("Proved"), SAFE_ROWS),
    "05-branch-before-release": (status_matcher("Counterexample"), BAD_ROWS),
    "06-equal-release-stays-active": (status_matcher("Counterexample"), BAD_ROWS),
    "07-wrong-audience-stays-active": (status_matcher("Counterexample"), BAD_ROWS),
}
WRAPPER_BY_CASE = {
    "04-authorized-release-first": "release_secret",
    "05-branch-before-release": "release_secret",
    "06-equal-release-stays-active": "release_bit",
    "07-wrong-audience-stays-active": "release_secret",
}
EXPECTED_POLICY_REVIEW = {
    "01-secret-branch": {"tag": "Complete"},
    "02-branchless-repair": {"tag": "Complete"},
    "03-missing-placement": {"tag": "Complete"},
    "04-authorized-release-first": {
        "tag": "FindingsMatcherV1",
        "required_lint_classes": ["IdentityReleaseOfHigh"],
    },
    "05-branch-before-release": {
        "tag": "FindingsMatcherV1",
        "required_lint_classes": ["IdentityReleaseOfHigh"],
    },
    "06-equal-release-stays-active": {"tag": "Complete"},
    "07-wrong-audience-stays-active": {"tag": "Complete"},
}

EXPECTED_DEPLOYMENT = {
    "tag": "Open",
    "args": [{"tag": "P4EvidenceProfileUnavailable"}],
}


def fail(message: str) -> None:
    raise SystemExit(message)


def normalized_llvm_text(path: Path) -> str:
    """Return the comparison form used to bind a mirror to its upstream sketch.

    The mirrored `capture-shape.ll` and the upstream `frozen.ll.sketch` carry
    deliberately different leading header comments, so the leading run of
    comment and blank lines is dropped. Every remaining line is right-stripped
    and trailing blank lines are removed, so a whitespace-only edit on either
    side is not spurious drift. Interior comments are NOT stripped: they are
    part of the shape being mirrored.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    start = 0
    while start < len(lines) and (
        not lines[start].strip() or lines[start].lstrip().startswith(";")
    ):
        start += 1
    body = [line.rstrip() for line in lines[start:]]
    while body and not body[-1]:
        body.pop()
    return "\n".join(body) + "\n"


def normalized_sha256(path: Path) -> str:
    text = normalized_llvm_text(path)
    if not text.strip():
        fail(f"{path}: normalized form is empty; refusing to digest it")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_source_binding(inventory: dict[str, object]) -> None:
    binding = inventory.get("source_binding")
    if not isinstance(binding, dict):
        fail("suite must declare a source_binding block")
    if binding.get("formatId") != SOURCE_BINDING_FORMAT_ID:
        fail(f"source_binding must use formatId {SOURCE_BINDING_FORMAT_ID}")
    if binding.get("source_root_env") != SOURCE_ROOT_ENV:
        fail(f"source_binding must name the {SOURCE_ROOT_ENV} environment variable")
    if binding.get("upstream_corpus_present_in_repo") is not False:
        fail("source_binding must record that the SPS corpus is outside this repo")


def check_upstream_sources(cases: list[dict[str, object]]) -> str:
    """Optionally re-derive each recorded upstream digest from the SPS corpus.

    The corpus is not part of this repository and will be absent on another
    machine, so this is enabled only by `SPS_LECTURE_SOURCE`. When it is unset
    the recorded `source_artifact_sha256` values are carried, not confirmed,
    and the returned line says so.
    """
    configured = os.environ.get(SOURCE_ROOT_ENV, "").strip()
    if not configured:
        return (
            "upstream source re-verification: SKIPPED "
            f"({SOURCE_ROOT_ENV} unset); the recorded source_artifact_sha256 "
            "values were carried from the inventory and were not re-derived "
            "from the SPS corpus"
        )
    root = Path(configured).expanduser()
    if not root.is_dir():
        fail(f"{SOURCE_ROOT_ENV}={configured} is not a directory")
    for case in cases:
        case_id = str(case["case_id"])
        recorded = case.get("source_artifact_sha256")
        if not isinstance(recorded, str) or len(recorded) != 64:
            fail(f"{case_id}: source_artifact_sha256 is missing or malformed")
        sketch = root / case_id / SOURCE_RELATIVE_NAME
        if not sketch.is_file():
            fail(
                f"{case_id}: {SOURCE_ROOT_ENV} is set but "
                f"{case_id}/{SOURCE_RELATIVE_NAME} is missing under {root}"
            )
        actual = normalized_sha256(sketch)
        if actual != recorded:
            fail(
                f"{case_id}: upstream source artifact normalized sha256 mismatch: "
                f"recorded {recorded}, computed {actual}"
            )
    return (
        f"upstream source re-verification: PERFORMED against {root}; "
        f"{len(cases)}/{len(cases)} normalized {SOURCE_RELATIVE_NAME} "
        "digests matched"
    )


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

    # The mirror/upstream binding, checked with no SPS corpus present. This is
    # the only check that sees an edit to the mirrored body that still parses
    # and still satisfies every structural rule below.
    recorded = case.get("capture_shape_sha256")
    if not isinstance(recorded, str) or len(recorded) != 64:
        fail(f"{case_id}: capture_shape_sha256 is missing or malformed")
    actual = normalized_sha256(path)
    if actual != recorded:
        fail(
            f"{case_id}: capture shape normalized sha256 mismatch: "
            f"recorded {recorded}, computed {actual}"
        )
    declared_source = case.get("source_artifact")
    if not isinstance(declared_source, str) or not declared_source.endswith(
        f"/{case_id}/{SOURCE_RELATIVE_NAME}"
    ):
        fail(f"{case_id}: source_artifact must name this case's upstream sketch")

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
    if case.get("tier") != {"tag": "PreflightV1"}:
        fail(f"{case_id}: lecture shape must remain a PreflightV1 fixture")
    model_matcher, rows = EXPECTED[case_id]
    if case.get("expected_model_status_matcher") != model_matcher:
        fail(f"{case_id}: wrong expected ModelStatus matcher")
    if case.get("expected_deployment_status") != EXPECTED_DEPLOYMENT:
        fail(f"{case_id}: wrong base-profile deployment status")
    if (
        case.get("expected_policy_review_status_matcher")
        != EXPECTED_POLICY_REVIEW[case_id]
    ):
        fail(f"{case_id}: wrong expected policy-review status")

    actual_rows = case.get("audit_all_expectations")
    if not isinstance(actual_rows, list) or len(actual_rows) != 3:
        fail(f"{case_id}: expected exactly three AuditAll rows")
    for actual, expected in zip(actual_rows, rows, strict=True):
        if actual != expected:
            fail(f"{case_id}: wrong or reordered AuditAll row: {actual!r}")
    check_shape(case, root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case", choices=CASE_IDS)
    args = parser.parse_args()
    root = args.root.resolve()
    inventory_path = root / "integration" / "Inputs" / "sps-lecture" / "cases.json"
    inventory = json.loads(inventory_path.read_text())
    if inventory.get("schema_version") != "SPS-Harness-Lecture-Fixture-Contracts-v2":
        fail("unsupported SPS lecture fixture schema")
    authority = inventory.get("authority")
    if not isinstance(authority, dict) or authority.get("claimable") is not False:
        fail("suite authority must be explicitly nonclaimable")
    if authority.get("tier") != {"tag": "PreflightV1"}:
        fail("suite authority must identify the preflight tier")
    if authority.get("checker_status") != "Unimplemented":
        fail("suite must not imply that the SPS checker exists")
    check_source_binding(inventory)

    cases = inventory.get("cases")
    if not isinstance(cases, list):
        fail("cases must be a list")
    by_id = {case.get("case_id"): case for case in cases if isinstance(case, dict)}
    if tuple(by_id) != CASE_IDS or len(by_id) != len(cases):
        fail("case inventory or order does not match the seven lecture cases")

    for case in cases:
        check_case(case, root)
    print(check_upstream_sources(cases))

    selected = (by_id[args.case],) if args.case else tuple(cases)
    for case in selected:
        matcher = case["expected_model_status_matcher"]
        assert isinstance(matcher, dict)
        expected = str(matcher["tag"])
        if expected == "Unknown":
            expected += f"({matcher['args'][0]['reasonClassId']})"
        print(
            f"verified {case['case_id']}: fixture-contract only; "
            f"tier=PreflightV1; claimable=false; ModelStatus=not-computed; "
            f"expected-matcher={expected}; capture-shape-sha256=verified"
        )


if __name__ == "__main__":
    main()
