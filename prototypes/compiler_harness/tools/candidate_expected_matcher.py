#!/usr/bin/env python3
"""Match a materialized SPS run against a candidate expected-run sidecar.

The candidate sidecar is a nonclaimable expectation contract.  This module
authenticates that contract through the sibling candidate ``artifact.json``
and ``artifact.bc``, validates the materialized Rev4.1 bundle/report boundary,
and compares only values exposed by those authenticated inputs.

Verifier execution authentication remains the caller's responsibility.  The
checkpoint runner must call this matcher only after authenticating the exact
verifier build and invocation.  In particular, a public SPS run report does
not expose a candidate sidecar's ``bad_state_class``.  Such a matcher is
reported as unresolved (and therefore never passes) until an authenticated
restricted-evidence adapter exists.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import check_sps_v2_bundle
import sps_interfaces


EXPECTED_FORMAT_ID = "SPS-Harness-Candidate-Expected-Run-v2"
ARTIFACT_FORMAT_ID = "SPS-Harness-Candidate-Artifact-v2"
SHA256_LENGTH = 64


class CandidateExpectedMatcherError(ValueError):
    """The expectation envelope or materialized run is malformed."""


@dataclass(frozen=True)
class CandidateExpectation:
    path: Path
    value: Mapping[str, Any]
    sidecar_sha256: str
    candidate_bitcode_sha256: str


@dataclass(frozen=True)
class CandidateExpectedMatch:
    """Result of comparing all publicly observable expectation fields.

    ``matched`` is intentionally false for both mismatches and unresolved
    protected-evidence requirements.  Callers must not treat
    ``observable_fields_match`` as a terminal security conclusion.
    """

    mismatches: tuple[str, ...]
    unresolved: tuple[str, ...]
    sidecar_sha256: str
    report_sha256: str
    artifact_identity_digest: str

    @property
    def observable_fields_match(self) -> bool:
        return not self.mismatches

    @property
    def matched(self) -> bool:
        return not self.mismatches and not self.unresolved


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_json(path: Path) -> tuple[Any, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise CandidateExpectedMatcherError(f"cannot read {path}: {error}") from error
    if raw.startswith(b"\xef\xbb\xbf"):
        raise CandidateExpectedMatcherError(f"{path}: UTF-8 BOM is forbidden")

    def pairs(rows: list[tuple[str, Any]]) -> OrderedDict[str, Any]:
        value: OrderedDict[str, Any] = OrderedDict()
        for key, item in rows:
            if key in value:
                raise CandidateExpectedMatcherError(
                    f"{path}: duplicate JSON key {key!r}"
                )
            value[key] = item
        return value

    def reject_float(value: str) -> Any:
        raise CandidateExpectedMatcherError(
            f"{path}: floating-point JSON number {value!r} is forbidden"
        )

    def reject_constant(value: str) -> Any:
        raise CandidateExpectedMatcherError(
            f"{path}: non-finite JSON constant {value!r} is forbidden"
        )

    try:
        return (
            json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=pairs,
                parse_float=reject_float,
                parse_constant=reject_constant,
            ),
            raw,
        )
    except UnicodeDecodeError as error:
        raise CandidateExpectedMatcherError(f"{path}: invalid UTF-8") from error
    except json.JSONDecodeError as error:
        raise CandidateExpectedMatcherError(f"{path}: invalid JSON: {error}") from error


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CandidateExpectedMatcherError(f"{context} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], context: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise CandidateExpectedMatcherError(
            f"{context} has wrong fields: missing={missing}, extra={extra}"
        )


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )


def _reason(value: Any, context: str) -> Mapping[str, Any]:
    result = _mapping(value, context)
    _exact_keys(result, {"reasonClassId"}, context)
    if not isinstance(result["reasonClassId"], str) or not result["reasonClassId"]:
        raise CandidateExpectedMatcherError(
            f"{context}.reasonClassId must be a nonempty string"
        )
    return result


def _validate_disposition(value: Any, context: str) -> None:
    disposition = _mapping(value, context)
    tag = disposition.get("tag")
    if tag in {"CandidateOnly", "Discharged"}:
        _exact_keys(disposition, {"tag"}, context)
        return
    if tag == "Unknown":
        _exact_keys(disposition, {"tag", "args"}, context)
        args = disposition["args"]
        if not isinstance(args, list) or len(args) != 1:
            raise CandidateExpectedMatcherError(
                f"{context}.args must contain one public reason"
            )
        _reason(args[0], f"{context}.args[0]")
        return
    raise CandidateExpectedMatcherError(f"{context}: unsupported disposition {tag!r}")


def _validate_expected(value: Mapping[str, Any], context: str) -> None:
    _exact_keys(
        value,
        {
            "entry",
            "audit_all_expectations",
            "expected_model_status",
            "expected_deployment_status",
            "expected_policy_review_status",
        },
        context,
    )
    if not isinstance(value["entry"], str) or not value["entry"]:
        raise CandidateExpectedMatcherError(f"{context}.entry must be nonempty")

    deployment = _mapping(
        value["expected_deployment_status"],
        f"{context}.expected_deployment_status",
    )
    if not isinstance(deployment.get("tag"), str):
        raise CandidateExpectedMatcherError(
            f"{context}.expected_deployment_status requires a tag"
        )
    policy = _mapping(
        value["expected_policy_review_status"],
        f"{context}.expected_policy_review_status",
    )
    if not isinstance(policy.get("tag"), str):
        raise CandidateExpectedMatcherError(
            f"{context}.expected_policy_review_status requires a tag"
        )

    model = _mapping(value["expected_model_status"], f"{context}.expected_model_status")
    model_tag = model.get("tag")
    if model_tag == "Proved":
        _exact_keys(model, {"tag"}, f"{context}.expected_model_status")
    elif model_tag == "Unknown":
        _exact_keys(model, {"tag", "args"}, f"{context}.expected_model_status")
        args = model["args"]
        if not isinstance(args, list) or not args:
            raise CandidateExpectedMatcherError(
                f"{context}.expected_model_status.args must be nonempty"
            )
        for ordinal, reason in enumerate(args):
            _reason(reason, f"{context}.expected_model_status.args[{ordinal}]")
    elif model_tag == "Counterexample":
        _exact_keys(
            model,
            {"tag", "receipt_matcher"},
            f"{context}.expected_model_status",
        )
        if model["receipt_matcher"] != {"tag": "FreshProtectedReceiptMatcherV2"}:
            raise CandidateExpectedMatcherError(
                f"{context}.expected_model_status has an unsupported receipt matcher"
            )
    else:
        raise CandidateExpectedMatcherError(
            f"{context}.expected_model_status has unsupported tag {model_tag!r}"
        )

    rows = value["audit_all_expectations"]
    if not isinstance(rows, list) or not rows:
        raise CandidateExpectedMatcherError(
            f"{context}.audit_all_expectations must be nonempty"
        )
    seen_coalitions: set[tuple[str, ...]] = set()
    for ordinal, raw_row in enumerate(rows):
        row_context = f"{context}.audit_all_expectations[{ordinal}]"
        row = _mapping(raw_row, row_context)
        _exact_keys(
            row,
            {"coalition", "query_outcome", "replay_expectation"},
            row_context,
        )
        coalition = row["coalition"]
        if (
            not isinstance(coalition, list)
            or any(not isinstance(item, str) or not item for item in coalition)
            or coalition != sorted(set(coalition))
        ):
            raise CandidateExpectedMatcherError(
                f"{row_context}.coalition must be sorted and duplicate-free"
            )
        coalition_key = tuple(coalition)
        if coalition_key in seen_coalitions:
            raise CandidateExpectedMatcherError(
                f"{row_context}.coalition duplicates another matcher"
            )
        seen_coalitions.add(coalition_key)

        outcome = _mapping(row["query_outcome"], f"{row_context}.query_outcome")
        replay = _mapping(
            row["replay_expectation"], f"{row_context}.replay_expectation"
        )
        outcome_tag = outcome.get("tag")
        replay_tag = replay.get("tag")
        if outcome_tag == "ConstructedResultMatcherV2":
            _exact_keys(
                outcome,
                {"tag", "raw_solver_result", "query_disposition"},
                f"{row_context}.query_outcome",
            )
            raw_result = outcome["raw_solver_result"]
            if raw_result not in {"SAT", "UNSAT", "UNKNOWN"}:
                raise CandidateExpectedMatcherError(
                    f"{row_context}.query_outcome has invalid raw_solver_result"
                )
            _validate_disposition(
                outcome["query_disposition"],
                f"{row_context}.query_outcome.query_disposition",
            )
            if raw_result == "SAT":
                _exact_keys(
                    replay,
                    {"tag", "bad_state_class"},
                    f"{row_context}.replay_expectation",
                )
                if replay_tag != "AcceptedBadStateRequiredV2" or not isinstance(
                    replay["bad_state_class"], str
                ) or not replay["bad_state_class"]:
                    raise CandidateExpectedMatcherError(
                        f"{row_context}: SAT requires a typed accepted-bad replay"
                    )
            elif replay_tag != "NotApplicableV2":
                raise CandidateExpectedMatcherError(
                    f"{row_context}: non-SAT constructed result cannot require replay"
                )
            else:
                _exact_keys(replay, {"tag"}, f"{row_context}.replay_expectation")
        elif outcome_tag == "NotConstructedResultMatcherV2":
            _exact_keys(
                outcome,
                {"tag", "reason"},
                f"{row_context}.query_outcome",
            )
            reason = _reason(outcome["reason"], f"{row_context}.query_outcome.reason")
            _exact_keys(
                replay,
                {"tag", "reason"},
                f"{row_context}.replay_expectation",
            )
            if replay_tag != "NotAvailableV2" or replay["reason"] != reason:
                raise CandidateExpectedMatcherError(
                    f"{row_context}: unavailable replay reason must match query reason"
                )
        else:
            raise CandidateExpectedMatcherError(
                f"{row_context}.query_outcome has unsupported tag {outcome_tag!r}"
            )


def load_candidate_expectation(expected_path: Path) -> CandidateExpectation:
    """Load and authenticate one checked-in candidate expectation envelope."""

    expected_path = Path(expected_path).resolve()
    candidate_dir = expected_path.parent
    artifact_path = candidate_dir / "artifact.json"
    bitcode_path = candidate_dir / "artifact.bc"
    if expected_path.name != "expected-report.json":
        raise CandidateExpectedMatcherError(
            "candidate expectation must be named expected-report.json"
        )
    sidecar_raw_value, sidecar_raw = _strict_json(expected_path)
    artifact_raw_value, _ = _strict_json(artifact_path)
    sidecar = _mapping(sidecar_raw_value, str(expected_path))
    artifact = _mapping(artifact_raw_value, str(artifact_path))

    required_sidecar_fields = {
        "format_id",
        "fixture_tier",
        "claimable_from_checked_in_pair",
        "required_checker_feature",
        "current_harness_status",
        "expected",
        "candidate_bitcode_sha256",
    }
    _exact_keys(sidecar, required_sidecar_fields, str(expected_path))
    if sidecar["format_id"] != EXPECTED_FORMAT_ID:
        raise CandidateExpectedMatcherError(
            f"{expected_path}: expected {EXPECTED_FORMAT_ID}"
        )
    if sidecar["fixture_tier"] != {"tag": "CandidateOnly"}:
        raise CandidateExpectedMatcherError(
            f"{expected_path}: expectation must remain CandidateOnly"
        )
    if sidecar["claimable_from_checked_in_pair"] is not False:
        raise CandidateExpectedMatcherError(
            f"{expected_path}: expectation must remain nonclaimable"
        )
    if sidecar["required_checker_feature"] != "sps-verifier":
        raise CandidateExpectedMatcherError(
            f"{expected_path}: required checker must be sps-verifier"
        )
    status = _mapping(sidecar["current_harness_status"], f"{expected_path}.status")
    if status.get("tag") != "PendingV2" or not isinstance(status.get("reasons"), list) or not status["reasons"]:
        raise CandidateExpectedMatcherError(
            f"{expected_path}: current status must remain PendingV2 with reasons"
        )
    candidate_digest = sidecar["candidate_bitcode_sha256"]
    if not _is_sha256(candidate_digest):
        raise CandidateExpectedMatcherError(
            f"{expected_path}: malformed candidate bitcode digest"
        )
    _validate_expected(_mapping(sidecar["expected"], f"{expected_path}.expected"), f"{expected_path}.expected")

    if artifact.get("format_id") != ARTIFACT_FORMAT_ID:
        raise CandidateExpectedMatcherError(
            f"{artifact_path}: expected {ARTIFACT_FORMAT_ID}"
        )
    if artifact.get("artifact_role") != "checked-in-bitcode-candidate":
        raise CandidateExpectedMatcherError(
            f"{artifact_path}: wrong artifact role"
        )
    if artifact.get("fixture_tier") != {"tag": "CandidateOnly"} or artifact.get("claimable") is not False:
        raise CandidateExpectedMatcherError(
            f"{artifact_path}: candidate artifact must remain nonclaimable"
        )
    envelope = _mapping(
        artifact.get("candidate_sidecar_sha256"),
        f"{artifact_path}.candidate_sidecar_sha256",
    )
    sidecar_digest = _sha256(sidecar_raw)
    if envelope.get("expected-report.json") != sidecar_digest:
        raise CandidateExpectedMatcherError(
            f"{expected_path}: digest does not match artifact.json envelope"
        )
    if artifact.get("candidate_bitcode_sha256") != candidate_digest:
        raise CandidateExpectedMatcherError(
            f"{expected_path}: candidate digest disagrees with artifact.json"
        )
    try:
        candidate_raw = bitcode_path.read_bytes()
    except OSError as error:
        raise CandidateExpectedMatcherError(
            f"cannot read {bitcode_path}: {error}"
        ) from error
    if _sha256(candidate_raw) != candidate_digest:
        raise CandidateExpectedMatcherError(
            f"{bitcode_path}: bytes do not match candidate digest"
        )
    return CandidateExpectation(
        path=expected_path,
        value=sidecar,
        sidecar_sha256=sidecar_digest,
        candidate_bitcode_sha256=candidate_digest,
    )


def _canonical_interface(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = sps_interfaces.require_canonical(raw)
    except (OSError, sps_interfaces.InterfaceError) as error:
        raise CandidateExpectedMatcherError(f"cannot load {path}: {error}") from error
    if not isinstance(value, Mapping):
        raise CandidateExpectedMatcherError(f"{path}: interface root must be an object")
    return value, raw


def _decode_canonical_record(value: Any, context: str) -> Mapping[str, Any]:
    wrapper = _mapping(value, context)
    exact_bytes = wrapper.get("canonicalBytes")
    if not isinstance(exact_bytes, str):
        raise CandidateExpectedMatcherError(f"{context}.canonicalBytes is missing")
    try:
        raw = bytes.fromhex(exact_bytes)
        decoded = sps_interfaces.require_canonical(raw)
    except (ValueError, sps_interfaces.InterfaceError) as error:
        raise CandidateExpectedMatcherError(
            f"{context}: invalid canonical bytes: {error}"
        ) from error
    return _mapping(decoded, context)


def _coalition_digest(coalition: Sequence[str]) -> str:
    return _sha256(sps_interfaces.canonical_bytes(list(coalition)))


def _entry_ids(policy: Mapping[str, Any], llvm_symbol: str) -> list[str]:
    rows = policy.get("entries")
    if not isinstance(rows, list):
        return []
    result: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = row.get("value")
        if (
            isinstance(row.get("key"), str)
            and isinstance(value, Mapping)
            and value.get("llvmSymbol") == llvm_symbol
        ):
            result.append(row["key"])
    return result


def _compare_status(
    expected: Mapping[str, Any],
    actual: Any,
    label: str,
    mismatches: list[str],
) -> str | None:
    actual_status = actual if isinstance(actual, Mapping) else {}
    if expected.get("tag") != "Counterexample":
        if actual_status != expected:
            mismatches.append(f"{label}: expected {dict(expected)!r}, got {actual!r}")
        return None
    if actual_status.get("tag") != "Counterexample":
        mismatches.append(f"{label}: expected Counterexample, got {actual!r}")
        return None
    args = actual_status.get("args")
    if not isinstance(args, list) or len(args) != 1 or not _is_sha256(args[0]):
        mismatches.append(
            f"{label}: Counterexample lacks one protected final-receipt identifier"
        )
        return None
    return args[0]


def _accepted_replay(aggregation: Mapping[str, Any]) -> Mapping[str, Any] | None:
    option = aggregation.get("acceptedBadReplay")
    if not isinstance(option, Mapping):
        return None
    if option.get("tag") == "None":
        return None
    value = option.get("value") if option.get("tag") == "Some" else None
    return value if isinstance(value, Mapping) else None


def _query_result_by_ordinal(public_report: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    rows = public_report.get("queryResults")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("queryOrdinal"), int):
            continue
        result[row["queryOrdinal"]] = row
    return result


def _match_audit_row(
    *,
    expected_row: Mapping[str, Any],
    query: Mapping[str, Any],
    result: Mapping[str, Any],
    accepted: Mapping[str, Any] | None,
    model_receipt: str | None,
    label: str,
    mismatches: list[str],
    unresolved: list[str],
) -> None:
    expected_outcome = _mapping(expected_row["query_outcome"], f"{label}.query_outcome")
    actual_outcome = result.get("outcome")
    actual_outcome = actual_outcome if isinstance(actual_outcome, Mapping) else {}
    expected_tag = expected_outcome["tag"]
    if expected_tag == "ConstructedResultMatcherV2":
        args = actual_outcome.get("args")
        if actual_outcome.get("tag") != "Constructed" or not isinstance(args, list) or len(args) != 1 or not isinstance(args[0], Mapping):
            mismatches.append(f"{label}: expected a constructed PONF result")
            return
        actual_result = args[0]
        if actual_result.get("rawSolverResult") != expected_outcome["raw_solver_result"]:
            mismatches.append(
                f"{label}: raw solver result expected {expected_outcome['raw_solver_result']!r}, "
                f"got {actual_result.get('rawSolverResult')!r}"
            )
        if actual_result.get("queryDisposition") != expected_outcome["query_disposition"]:
            mismatches.append(
                f"{label}: query disposition expected {expected_outcome['query_disposition']!r}, "
                f"got {actual_result.get('queryDisposition')!r}"
            )
    elif (
        actual_outcome.get("tag") != "NotConstructedV2"
        or actual_outcome.get("reason") != expected_outcome["reason"]
    ):
        mismatches.append(
            f"{label}: expected NotConstructedV2 with reason {expected_outcome['reason']!r}"
        )

    expected_replay = _mapping(
        expected_row["replay_expectation"], f"{label}.replay_expectation"
    )
    replay_tag = expected_replay["tag"]
    actual_is_this_query = (
        accepted is not None
        and accepted.get("queryOrdinal") == result.get("queryOrdinal")
    )
    if replay_tag in {"NotApplicableV2", "NotAvailableV2"}:
        if actual_is_this_query:
            mismatches.append(f"{label}: unexpectedly has an accepted-bad replay")
        return

    if accepted is None:
        mismatches.append(f"{label}: expected an accepted-bad replay, got None")
        return
    if not actual_is_this_query:
        mismatches.append(
            f"{label}: accepted-bad replay binds query ordinal "
            f"{accepted.get('queryOrdinal')!r}, not {result.get('queryOrdinal')!r}"
        )
        return
    if accepted.get("query") != query:
        mismatches.append(f"{label}: accepted-bad replay query does not equal schedule query")
    receipt = accepted.get("finalReceiptId")
    protected = accepted.get("protectedEvidence")
    if not _is_sha256(receipt) or not isinstance(protected, Mapping) or protected.get("receiptId") != receipt:
        mismatches.append(f"{label}: accepted-bad replay has an invalid receipt binding")
    if model_receipt is not None and receipt != model_receipt:
        mismatches.append(
            f"{label}: replay receipt {receipt!r} does not match ModelStatus receipt {model_receipt!r}"
        )

    # Fail closed.  The public report exposes only a digest and receipt for the
    # first bad state; it does not expose this candidate-only semantic class.
    unresolved.append(
        f"{label}: expected bad_state_class {expected_replay['bad_state_class']!r}, "
        "but no authenticated restricted-evidence projection is available"
    )


def match_candidate_expected_run(
    expected_path: Path,
    materialized_bundle: Path,
    report_path: Path,
) -> CandidateExpectedMatch:
    """Compare a validated materialized run with a digest-bound expectation.

    This function validates the public materialized boundary itself.  It does
    not execute or authenticate the verifier; callers must do that before a
    successful result is allowed to influence terminal test status.
    """

    expectation = load_candidate_expectation(Path(expected_path))
    materialized_bundle = Path(materialized_bundle).resolve()
    report_path = Path(report_path).resolve()
    try:
        # The boundary validator's success message is useful as a CLI but would
        # be surprising output from a library function.
        with redirect_stdout(io.StringIO()):
            check_sps_v2_bundle.check_bundle(materialized_bundle, report_path)
    except (
        OSError,
        ValueError,
        sps_interfaces.InterfaceError,
    ) as error:
        raise CandidateExpectedMatcherError(
            f"materialized SPS bundle/report boundary is invalid: {error}"
        ) from error

    report, report_raw = _canonical_interface(report_path)
    aggregation, _ = _canonical_interface(
        materialized_bundle / "aggregation-input.sps.json"
    )
    identity, identity_raw = _canonical_interface(
        materialized_bundle / "artifact-identity.sps.json"
    )
    evidence, _ = _canonical_interface(
        materialized_bundle / "identity-evidence.sps.json"
    )
    policy = _decode_canonical_record(evidence.get("policy"), "identity evidence policy")

    mismatches: list[str] = []
    unresolved: list[str] = []
    expected = _mapping(expectation.value["expected"], "candidate expected run")
    if report.get("tag") != "CompletedV2":
        mismatches.append(
            f"SPSRunReportV2: expected CompletedV2, got {report.get('tag')!r}"
        )
        return CandidateExpectedMatch(
            mismatches=tuple(mismatches),
            unresolved=(),
            sidecar_sha256=expectation.sidecar_sha256,
            report_sha256=_sha256(report_raw),
            artifact_identity_digest=_sha256(identity_raw),
        )
    public_report = _mapping(report.get("report"), "completed public report")
    model_receipt = _compare_status(
        _mapping(expected["expected_model_status"], "expected ModelStatus"),
        public_report.get("modelStatus"),
        "ModelStatus",
        mismatches,
    )
    for expected_key, actual_key, label in (
        ("expected_deployment_status", "deploymentStatus", "DeploymentStatus"),
        ("expected_policy_review_status", "policyReviewStatus", "PolicyReviewStatus"),
    ):
        expected_status = expected[expected_key]
        actual_status = public_report.get(actual_key)
        if actual_status != expected_status:
            mismatches.append(
                f"{label}: expected {expected_status!r}, got {actual_status!r}"
            )

    entry_ids = _entry_ids(policy, expected["entry"])
    if len(entry_ids) != 1:
        mismatches.append(
            f"entry: expected exactly one canonical policy entry with llvmSymbol "
            f"{expected['entry']!r}, got {entry_ids!r}"
        )
        return CandidateExpectedMatch(
            mismatches=tuple(mismatches),
            unresolved=tuple(unresolved),
            sidecar_sha256=expectation.sidecar_sha256,
            report_sha256=_sha256(report_raw),
            artifact_identity_digest=_sha256(identity_raw),
        )
    entry_id = entry_ids[0]
    schedule = _mapping(public_report.get("querySchedule"), "public query schedule")
    queries = schedule.get("queries")
    queries = queries if isinstance(queries, list) else []
    results = _query_result_by_ordinal(public_report)

    actual_audit: dict[str, tuple[int, Mapping[str, Any]]] = {}
    for ordinal, raw_query in enumerate(queries):
        if not isinstance(raw_query, Mapping):
            continue
        if raw_query.get("queryKind") != {"tag": "AuditAll"}:
            continue
        if raw_query.get("entryScope") != {"tag": "Some", "value": entry_id}:
            continue
        coalition_scope = raw_query.get("coalitionScope")
        if (
            isinstance(coalition_scope, Mapping)
            and coalition_scope.get("tag") == "ConcreteCoalition"
            and isinstance(coalition_scope.get("coalitionId"), str)
        ):
            actual_audit[coalition_scope["coalitionId"]] = (ordinal, raw_query)

    expected_rows = expected["audit_all_expectations"]
    expected_ids = {
        _coalition_digest(row["coalition"]): row for row in expected_rows
    }
    missing = sorted(set(expected_ids) - set(actual_audit))
    extra = sorted(set(actual_audit) - set(expected_ids))
    for coalition_id in missing:
        coalition = expected_ids[coalition_id]["coalition"]
        mismatches.append(
            f"AuditAll coalition {coalition!r}: no schedule row for digest {coalition_id}"
        )
    for coalition_id in extra:
        mismatches.append(
            f"AuditAll: unexpected schedule coalition digest {coalition_id} for entry {entry_id}"
        )

    accepted = _accepted_replay(aggregation)
    for coalition_id in sorted(set(expected_ids) & set(actual_audit)):
        expected_row = expected_ids[coalition_id]
        ordinal, query = actual_audit[coalition_id]
        result = results.get(ordinal)
        label = f"AuditAll coalition {expected_row['coalition']!r}"
        if result is None:
            mismatches.append(f"{label}: missing query result at ordinal {ordinal}")
            continue
        _match_audit_row(
            expected_row=expected_row,
            query=query,
            result=result,
            accepted=accepted,
            model_receipt=model_receipt,
            label=label,
            mismatches=mismatches,
            unresolved=unresolved,
        )

    return CandidateExpectedMatch(
        mismatches=tuple(mismatches),
        unresolved=tuple(unresolved),
        sidecar_sha256=expectation.sidecar_sha256,
        report_sha256=_sha256(report_raw),
        artifact_identity_digest=_sha256(identity_raw),
    )


__all__ = [
    "CandidateExpectation",
    "CandidateExpectedMatch",
    "CandidateExpectedMatcherError",
    "load_candidate_expectation",
    "match_candidate_expected_run",
]
