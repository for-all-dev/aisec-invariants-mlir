#!/usr/bin/env python3
"""Evaluate the Rev4.1 module-requiredness matrix without issuing an SPS result.

The input and output are harness-owned expectation records.  SPS owns the
reason, blocker-scope, reporting-reason, and policy-status spellings; this
checker obtains those spellings from the vendored Rev4.1 interface registry
and constructs every blocker through ``sps_aggregation.BlockerRecordV2``.

This is deliberately not a verifier.  Its output is always nonclaimable and
always carries the ``NotComputed`` harness sentinel.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import sps_aggregation
import sps_interfaces


CATALOG_FORMAT = "SPS-Harness-Required-Module-Cases-v2"
INPUT_FORMAT = "SPS-Harness-Required-Module-Input-v2"
OUTPUT_FORMAT = "SPS-Harness-Required-Module-Evaluation-v2"
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
INPUT_FIELDS = {
    "formatId",
    "requiredScopes",
    "candidateSearch",
    "diagnostics",
    "timingRiskRecords",
    "completedRunRequested",
    "policyReview",
    "deploymentClosureAttempted",
    "backendControlDelta",
    "proofGateState",
}
EXPECTATION_FIELDS = {
    "proofCompletionReasons",
    "runFinalizationReasons",
    "requiredModulesReadyForCompletion",
    "backendControlDeltaRequired",
    "deploymentClosureEvidenceReady",
    "proofGateState",
}
PROOF_GATE_STATES = {"Open", "WouldYieldProvedIfAuthoritativeRun"}

_REGISTRY = sps_interfaces.load_default_registry()
_PUBLIC_REASONS = set(_REGISTRY.enum_values("PublicReasonClassesV2"))
_BLOCKER_SCOPES = set(_REGISTRY.enum_values("BlockerScopeV2"))
_REPORTING_REASONS = set(_REGISTRY.union_variants("SPSReportingFailureReasonV2"))
_POLICY_STATUSES = set(_REGISTRY.union_variants("PolicyReviewStatusV2"))

if "DiagnosticHealthFailure" not in _PUBLIC_REASONS:
    raise sps_interfaces.InterfaceError(
        "vendored PublicReasonClassesV2 omits DiagnosticHealthFailure"
    )
if {"ProofCompletion", "RunFinalization"} - _BLOCKER_SCOPES:
    raise sps_interfaces.InterfaceError(
        "vendored BlockerScopeV2 omits a required module-matrix scope"
    )
if "EvidenceFinalizationFailure" not in _REPORTING_REASONS:
    raise sps_interfaces.InterfaceError(
        "vendored SPSReportingFailureReasonV2 omits EvidenceFinalizationFailure"
    )


class RequiredModuleError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RequiredModuleError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _load(path: Path) -> object:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object
        )
    except OSError as error:
        raise RequiredModuleError(f"cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise RequiredModuleError(f"invalid JSON in {path}: {error.msg}") from error


def _exact_fields(value: object, fields: set[str], context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RequiredModuleError(f"{context} must be an object")
    if set(value) != fields:
        raise RequiredModuleError(
            f"{context} has wrong fields "
            f"(missing={sorted(fields - set(value))}, extra={sorted(set(value) - fields)})"
        )
    return value


def _identifier(value: object, context: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise RequiredModuleError(f"{context} must be an identifier")
    return value


def _identifier_list(value: object, context: str) -> list[str]:
    if not isinstance(value, list):
        raise RequiredModuleError(f"{context} must be an array")
    result = [_identifier(item, context) for item in value]
    if result != sorted(set(result)):
        raise RequiredModuleError(f"{context} must be sorted and duplicate-free")
    return result


def _scoped_rows(
    value: object, context: str, extra_fields: set[str]
) -> dict[tuple[str, str], Mapping[str, Any]]:
    if not isinstance(value, list):
        raise RequiredModuleError(f"{context} must be an array")
    rows: dict[tuple[str, str], Mapping[str, Any]] = {}
    fields = {"entryId", "coalitionId"} | extra_fields
    for ordinal, item in enumerate(value):
        row = _exact_fields(item, fields, f"{context}[{ordinal}]")
        key = (
            _identifier(row["entryId"], f"{context}[{ordinal}].entryId"),
            _identifier(row["coalitionId"], f"{context}[{ordinal}].coalitionId"),
        )
        if key in rows:
            raise RequiredModuleError(f"{context} contains duplicate scope {key}")
        rows[key] = row
    if list(rows) != sorted(rows):
        raise RequiredModuleError(f"{context} must be sorted by entryId/coalitionId")
    return rows


def _option(value: object, context: str) -> tuple[bool, Mapping[str, Any] | None]:
    if not isinstance(value, Mapping) or set(value) not in ({"tag"}, {"tag", "value"}):
        raise RequiredModuleError(f"{context} must be a closed None/Some option")
    if value.get("tag") == "None" and set(value) == {"tag"}:
        return False, None
    if value.get("tag") == "Some" and set(value) == {"tag", "value"}:
        if not isinstance(value["value"], Mapping):
            raise RequiredModuleError(f"{context}.value must be an object")
        return True, value["value"]
    raise RequiredModuleError(f"{context} must be a closed None/Some option")


def _candidate_search(value: object) -> str:
    if not isinstance(value, Mapping):
        raise RequiredModuleError("candidateSearch must be an object")
    if value == {"tag": "NotRun"}:
        return "NotRun"
    row = _exact_fields(value, {"tag", "findings"}, "candidateSearch")
    if row["tag"] != "Completed":
        raise RequiredModuleError("candidateSearch.tag must be NotRun or Completed")
    _identifier_list(row["findings"], "candidateSearch.findings")
    return "Completed"


def _policy_review(value: object) -> tuple[bool, str | None]:
    present, payload = _option(value, "policyReview")
    if not present:
        return False, None
    assert payload is not None
    row = _exact_fields(payload, {"statusTag", "findings"}, "policyReview.value")
    status = row["statusTag"]
    if status not in _POLICY_STATUSES:
        raise RequiredModuleError(
            f"policyReview.value.statusTag must name vendored PolicyReviewStatus: "
            f"{sorted(_POLICY_STATUSES)}"
        )
    _identifier_list(row["findings"], "policyReview.value.findings")
    return True, str(status)


def _backend_delta(value: object) -> bool:
    present, payload = _option(value, "backendControlDelta")
    if not present:
        return False
    assert payload is not None
    row = _exact_fields(payload, {"findings"}, "backendControlDelta.value")
    _identifier_list(row["findings"], "backendControlDelta.value.findings")
    return True


def _blocker(
    *, scope: sps_aggregation.BlockerScope, reason: str, phase: int,
    schedule: int | None
) -> sps_aggregation.BlockerRecordV2:
    return sps_aggregation.make_blocker(
        scope=scope,
        reason=reason,
        phase_ordinal=phase,
        schedule_ordinal=schedule,
    )


def evaluate(value: object) -> dict[str, Any]:
    record = _exact_fields(value, INPUT_FIELDS, "required-module input")
    if record["formatId"] != INPUT_FORMAT:
        raise RequiredModuleError(f"formatId must be {INPUT_FORMAT}")

    required_rows = _scoped_rows(record["requiredScopes"], "requiredScopes", set())
    if not required_rows:
        raise RequiredModuleError("requiredScopes must not be empty")
    required = tuple(required_rows)

    candidate_disposition = _candidate_search(record["candidateSearch"])
    diagnostics = _scoped_rows(
        record["diagnostics"],
        "diagnostics",
        {"health", "conclusion", "findings"},
    )
    timing = _scoped_rows(
        record["timingRiskRecords"], "timingRiskRecords", {"findings"}
    )
    extra_diagnostics = sorted(set(diagnostics) - set(required))
    extra_timing = sorted(set(timing) - set(diagnostics))
    if extra_diagnostics:
        raise RequiredModuleError(
            f"diagnostics contain non-required scopes: {extra_diagnostics}"
        )
    if extra_timing:
        raise RequiredModuleError(
            f"timingRiskRecords lack a preceding diagnostic: {extra_timing}"
        )

    proof_blockers: list[sps_aggregation.BlockerRecordV2] = []
    for ordinal, key in enumerate(required):
        row = diagnostics.get(key)
        if row is None:
            proof_blockers.append(
                _blocker(
                    scope=sps_aggregation.BlockerScope.PROOF_COMPLETION,
                    reason="DiagnosticHealthFailure",
                    phase=20,
                    schedule=ordinal,
                )
            )
            continue
        health = row["health"]
        if health not in {"Healthy", "Malformed", "Stale", "Incomplete"}:
            raise RequiredModuleError(
                f"diagnostics[{key}].health must be Healthy, Malformed, Stale, or Incomplete"
            )
        _identifier(row["conclusion"], f"diagnostics[{key}].conclusion")
        _identifier_list(row["findings"], f"diagnostics[{key}].findings")
        if health != "Healthy":
            proof_blockers.append(
                _blocker(
                    scope=sps_aggregation.BlockerScope.PROOF_COMPLETION,
                    reason="DiagnosticHealthFailure",
                    phase=20,
                    schedule=ordinal,
                )
            )

    finalization_blockers: list[sps_aggregation.BlockerRecordV2] = []
    # M21 follows every M20 run that produced a record.  If M20 is absent, the
    # M20 health blocker above is the precise failure; a phantom M21 record is
    # neither required nor admitted.
    for key, row in diagnostics.items():
        _identifier_list(row["findings"], f"diagnostics[{key}].findings")
        if key not in timing:
            finalization_blockers.append(
                _blocker(
                    scope=sps_aggregation.BlockerScope.RUN_FINALIZATION,
                    reason="EvidenceFinalizationFailure",
                    phase=21,
                    schedule=required.index(key),
                )
            )
    for key, row in timing.items():
        _identifier_list(row["findings"], f"timingRiskRecords[{key}].findings")

    if not isinstance(record["completedRunRequested"], bool):
        raise RequiredModuleError("completedRunRequested must be Boolean")
    policy_present, policy_status = _policy_review(record["policyReview"])
    if record["completedRunRequested"] and not policy_present:
        finalization_blockers.append(
            _blocker(
                scope=sps_aggregation.BlockerScope.RUN_FINALIZATION,
                reason="EvidenceFinalizationFailure",
                phase=22,
                schedule=None,
            )
        )

    if not isinstance(record["deploymentClosureAttempted"], bool):
        raise RequiredModuleError("deploymentClosureAttempted must be Boolean")
    backend_present = _backend_delta(record["backendControlDelta"])
    backend_required = record["deploymentClosureAttempted"]
    deployment_ready = not backend_required or backend_present

    upstream_proof_gate_state = record["proofGateState"]
    if upstream_proof_gate_state not in PROOF_GATE_STATES:
        raise RequiredModuleError(
            f"proofGateState must be one of {sorted(PROOF_GATE_STATES)}"
        )
    # The input names the state supplied by the proof/query layer.  Mandatory
    # diagnostic health is a completion gate, so an unhealthy or absent M20
    # record forces the effective proof axis open regardless of that supplied
    # state.
    proof_gate_state = "Open" if proof_blockers else upstream_proof_gate_state

    return {
        "formatId": OUTPUT_FORMAT,
        "claimable": False,
        "modelStatus": {"tag": "NotComputed"},
        "candidateSearchDisposition": candidate_disposition,
        "candidateSearchEffect": "DiscoveryOnlyV2",
        "diagnosticConclusionEffect": "NoModelVoteV2",
        "timingFindingEffect": "NoModelVoteV2",
        "policyFindingEffect": "IndependentAxisV2",
        "proofGateState": proof_gate_state,
        "proofCompletionBlockers": [item.as_json() for item in proof_blockers],
        "runFinalizationBlockers": [
            item.as_json() for item in finalization_blockers
        ],
        "requiredModulesReadyForCompletion": not proof_blockers
        and not finalization_blockers,
        "policyReviewPresent": policy_present,
        "policyReviewStatusTag": policy_status,
        "backendControlDeltaRequired": backend_required,
        "deploymentClosureEvidenceReady": deployment_ready,
    }


def _reasons(records: object) -> list[str]:
    assert isinstance(records, list)
    result: list[str] = []
    for record in records:
        typed = sps_aggregation.BlockerRecordV2.from_json(record)
        reason = typed.reason_class_id or typed.reporting_reason_tag
        assert reason is not None
        result.append(reason)
    return result


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "proofCompletionReasons": _reasons(result["proofCompletionBlockers"]),
        "runFinalizationReasons": _reasons(result["runFinalizationBlockers"]),
        "requiredModulesReadyForCompletion": result[
            "requiredModulesReadyForCompletion"
        ],
        "backendControlDeltaRequired": result["backendControlDeltaRequired"],
        "deploymentClosureEvidenceReady": result[
            "deploymentClosureEvidenceReady"
        ],
        "proofGateState": result["proofGateState"],
    }


def check_catalog(value: object, selected: set[str]) -> list[tuple[str, dict[str, Any]]]:
    catalog = _exact_fields(value, {"formatId", "cases"}, "catalog")
    if catalog["formatId"] != CATALOG_FORMAT:
        raise RequiredModuleError(f"catalog formatId must be {CATALOG_FORMAT}")
    if not isinstance(catalog["cases"], list):
        raise RequiredModuleError("catalog.cases must be an array")
    results: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for ordinal, item in enumerate(catalog["cases"]):
        case = _exact_fields(
            item, {"caseId", "input", "expected"}, f"cases[{ordinal}]"
        )
        case_id = _identifier(case["caseId"], f"cases[{ordinal}].caseId")
        if case_id in seen:
            raise RequiredModuleError(f"duplicate caseId {case_id}")
        seen.add(case_id)
        if selected and case_id not in selected:
            continue
        expected = _exact_fields(
            case["expected"], EXPECTATION_FIELDS, f"{case_id}.expected"
        )
        result = evaluate(case["input"])
        actual = _summary(result)
        if actual != dict(expected):
            raise RequiredModuleError(
                f"{case_id}: expectation mismatch\n"
                f"expected={dict(expected)!r}\nactual={actual!r}"
            )
        results.append((case_id, result))
    missing = sorted(selected - seen)
    if missing:
        raise RequiredModuleError(f"unknown selected cases: {missing}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--dump-json", action="store_true")
    arguments = parser.parse_args()
    try:
        results = check_catalog(_load(arguments.catalog), set(arguments.case))
    except (RequiredModuleError, sps_interfaces.InterfaceError) as error:
        raise SystemExit(error) from error
    for case_id, result in results:
        if arguments.dump_json:
            print(
                json.dumps(
                    {"caseId": case_id, "evaluation": result},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            continue
        summary = _summary(result)
        print(
            f"verified nonclaimable module matrix: {case_id}; "
            f"proof={summary['proofCompletionReasons']}; "
            f"finalization={summary['runFinalizationReasons']}; "
            f"completion-ready={str(summary['requiredModulesReadyForCompletion']).lower()}; "
            f"backend-required={str(summary['backendControlDeltaRequired']).lower()}; "
            f"deployment-ready={str(summary['deploymentClosureEvidenceReady']).lower()}; "
            f"proof-axis={summary['proofGateState']}; model=NotComputed"
        )


if __name__ == "__main__":
    main()
