#!/usr/bin/env python3
"""Typed harness evaluation of the SPS Rev4.1 aggregation interface.

SPS owns the wire shape.  Every input is first validated as the vendored
``AggregationInputV2`` interface; the harness owns only expectation matchers
and this small executable model of ``SPS-Model-Aggregation-v2``.  It does not
establish WFInputs, NFConforms, replay validity, or an authoritative result.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

import sps_interfaces


OPEN_MODEL_OBLIGATIONS = "OpenModelObligations"
ACCEPTED_REPLAY_INVALIDATING_ERROR = (
    "AcceptedReplayConflictsWithReplayInvalidatingBlocker"
)
ZERO_DIGEST = "0" * 64
DEFAULT_PROOF_CONFIGURATION_DIGEST = "1" * 64
DEFAULT_QUERY_SCHEDULE_DIGEST = "2" * 64
DEFAULT_FIRST_BAD_STATE_DIGEST = "3" * 64
DEFAULT_COALITION_ID = (
    "56787980b512fa492fc5300a2ca2703f7f1d020a9b925d80b92d6eddd2eafc69"
)

_REGISTRY = sps_interfaces.load_default_registry()


class AggregationInputError(ValueError):
    """A malformed or semantically inconsistent aggregation input."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class BlockerScope(str, Enum):
    REPLAY_INVALIDATING = "ReplayInvalidating"
    PROOF_COMPLETION = "ProofCompletion"
    RUN_FINALIZATION = "RunFinalization"


_SCOPE_ORDER = _REGISTRY.enum_values("BlockerScopeV2")
if tuple(scope.value for scope in BlockerScope) != _SCOPE_ORDER:
    raise sps_interfaces.InterfaceError(
        "local aggregation semantics do not cover the vendored BlockerScopeV2 order"
    )


def _interface_error(code: str, error: Exception) -> AggregationInputError:
    return AggregationInputError(code, str(error))


@dataclass(frozen=True, slots=True)
class BlockerRecordV2:
    """Validated wrapper around the authoritative SPS BlockerRecordV2 wire object."""

    _wire: dict[str, object]

    @classmethod
    def from_json(cls, value: object) -> "BlockerRecordV2":
        try:
            _REGISTRY.validate_root(value, "BlockerRecordV2")
        except sps_interfaces.InterfaceError as error:
            raise _interface_error("MalformedBlockerRecordV2", error) from error
        assert isinstance(value, dict)
        scope = BlockerScope(value["scope"])
        reason = value["reason"]
        assert isinstance(reason, dict)
        reporting = reason.get("tag") == "ReportingBlocker"
        if (scope is BlockerScope.RUN_FINALIZATION) != reporting:
            raise AggregationInputError(
                "XF-AGG-002",
                "RunFinalization requires ReportingBlocker and other scopes "
                "require ModelBlocker",
            )
        return cls(copy.deepcopy(value))

    @property
    def scope(self) -> BlockerScope:
        return BlockerScope(self._wire["scope"])

    @property
    def reason_class_id(self) -> str | None:
        reason = self._wire["reason"]
        assert isinstance(reason, dict)
        if reason["tag"] != "ModelBlocker":
            return None
        detail = reason["reason"]
        assert isinstance(detail, dict)
        value = detail["reasonClassId"]
        assert isinstance(value, str)
        return value

    @property
    def reporting_reason_tag(self) -> str | None:
        reason = self._wire["reason"]
        assert isinstance(reason, dict)
        if reason["tag"] != "ReportingBlocker":
            return None
        detail = reason["reason"]
        assert isinstance(detail, dict)
        value = detail["tag"]
        assert isinstance(value, str)
        return value

    def as_json(self) -> dict[str, object]:
        return copy.deepcopy(self._wire)

    def canonical_bytes(self) -> bytes:
        return sps_interfaces.canonical_bytes(self._wire)


@dataclass(frozen=True, slots=True)
class AcceptedBadReplayV2:
    """Validated restricted replay token from the authoritative SPS interface."""

    _wire: dict[str, object]

    @classmethod
    def from_json(cls, value: object) -> "AcceptedBadReplayV2":
        try:
            _REGISTRY.validate_root(value, "AcceptedBadReplayV2")
        except sps_interfaces.InterfaceError as error:
            raise _interface_error("MalformedAcceptedBadReplayV2", error) from error
        assert isinstance(value, dict)
        evidence = value["protectedEvidence"]
        assert isinstance(evidence, dict)
        if value["finalReceiptId"] != evidence["receiptId"]:
            raise AggregationInputError(
                "ReplayReceiptBindingMismatch",
                "AcceptedBadReplayV2.finalReceiptId must equal protectedEvidence.receiptId",
            )
        semantic_failures = _REGISTRY.semantic_failures(value, "AcceptedBadReplayV2")
        if semantic_failures:
            raise AggregationInputError(
                semantic_failures[0],
                "AcceptedBadReplayV2 violates " + ", ".join(semantic_failures),
            )
        return cls(copy.deepcopy(value))

    @property
    def receipt_id(self) -> str:
        value = self._wire["finalReceiptId"]
        assert isinstance(value, str)
        return value

    @property
    def artifact_identity_digest(self) -> str:
        value = self._wire["artifactIdentityDigest"]
        assert isinstance(value, str)
        return value

    @property
    def proof_configuration_digest(self) -> str:
        value = self._wire["proofConfigurationDigest"]
        assert isinstance(value, str)
        return value

    @property
    def query_schedule_digest(self) -> str:
        value = self._wire["queryScheduleDigest"]
        assert isinstance(value, str)
        return value

    def as_json(self) -> dict[str, object]:
        return copy.deepcopy(self._wire)


@dataclass(frozen=True, slots=True)
class AggregationInputV2:
    artifact_identity_digest: str
    proof_configuration_digest: str
    query_schedule_digest: str
    accepted_bad_replay: AcceptedBadReplayV2 | None
    blockers: tuple[BlockerRecordV2, ...]
    all_required_gates_closed: bool
    _wire: dict[str, object]

    @classmethod
    def from_json(cls, value: object) -> "AggregationInputV2":
        try:
            _REGISTRY.validate_root(value, "AggregationInputV2")
        except sps_interfaces.InterfaceError as error:
            raise _interface_error("MalformedAggregationInputV2", error) from error
        assert isinstance(value, dict)
        accepted_option = value["acceptedBadReplay"]
        assert isinstance(accepted_option, dict)
        accepted = (
            None
            if accepted_option["tag"] == "None"
            else AcceptedBadReplayV2.from_json(accepted_option["value"])
        )
        blocker_values = value["blockers"]
        assert isinstance(blocker_values, list)
        blockers = tuple(BlockerRecordV2.from_json(item) for item in blocker_values)
        encoded = tuple(blocker.canonical_bytes() for blocker in blockers)
        if encoded != tuple(sorted(encoded)):
            raise AggregationInputError(
                "NoncanonicalBlockerRecordsV2",
                "BlockerRecordV2 rows must be ordered by canonical element bytes",
            )
        if len(encoded) != len(set(encoded)):
            raise AggregationInputError(
                "NoncanonicalBlockerRecordsV2",
                "BlockerRecordV2 rows must be duplicate-free",
            )

        artifact_digest = value["artifactIdentityDigest"]
        proof_digest = value["proofConfigurationDigest"]
        schedule_digest = value["queryScheduleDigest"]
        assert isinstance(artifact_digest, str)
        assert isinstance(proof_digest, str)
        assert isinstance(schedule_digest, str)
        if accepted is not None and (
            accepted.artifact_identity_digest != artifact_digest
            or accepted.proof_configuration_digest != proof_digest
            or accepted.query_schedule_digest != schedule_digest
        ):
            raise AggregationInputError(
                "XF-REPLAY-002",
                "AcceptedBadReplayV2 identity and schedule digests must equal "
                "their AggregationInputV2 bindings",
            )

        semantic_failures = _REGISTRY.semantic_failures(value, "AggregationInputV2")
        for rule in semantic_failures:
            if rule != "XF-REPLAY-001":
                raise AggregationInputError(rule, f"AggregationInputV2 violates {rule}")
        gates = value["allRequiredGatesClosed"]
        assert isinstance(gates, bool)
        return cls(
            artifact_digest,
            proof_digest,
            schedule_digest,
            accepted,
            blockers,
            gates,
            copy.deepcopy(value),
        )

    def as_json(self) -> dict[str, object]:
        return copy.deepcopy(self._wire)


@dataclass(frozen=True, slots=True)
class CompletedAggregationV2:
    model_status: dict[str, object]
    blockers: tuple[BlockerRecordV2, ...]


@dataclass(frozen=True, slots=True)
class ReportingFailedAggregationV2:
    """Run-finalization outcome; deliberately contains no ModelStatus field."""

    blockers: tuple[BlockerRecordV2, ...]


AggregationOutcomeV2: TypeAlias = CompletedAggregationV2 | ReportingFailedAggregationV2


def make_blocker(
    *,
    scope: BlockerScope,
    reason: str,
    phase_ordinal: int = 0,
    schedule_ordinal: int | None = None,
    restricted_detail_digest: str = ZERO_DIGEST,
) -> BlockerRecordV2:
    """Build structurally authoritative expectation evidence for local readers."""

    reason_value: dict[str, object]
    if scope is BlockerScope.RUN_FINALIZATION:
        reason_value = {
            "tag": "ReportingBlocker",
            "reason": {"tag": reason},
        }
    else:
        reason_value = {
            "tag": "ModelBlocker",
            "reason": {"reasonClassId": reason},
        }
    schedule: dict[str, object] = (
        {"tag": "None"}
        if schedule_ordinal is None
        else {"tag": "Some", "value": schedule_ordinal}
    )
    return BlockerRecordV2.from_json(
        {
            "formatId": "SPS-Blocker-Record-v2",
            "scope": scope.value,
            "phaseOrdinal": phase_ordinal,
            "scheduleOrdinal": schedule,
            "reason": reason_value,
            "restrictedDetailDigest": restricted_detail_digest,
        }
    )


def proof_completion_blockers(reasons: Iterable[object]) -> tuple[BlockerRecordV2, ...]:
    """Construct typed no-replay blockers for legacy candidate expectations."""

    values = tuple(reasons)
    if any(not isinstance(reason, str) or not reason for reason in values):
        raise AggregationInputError(
            "MalformedBlockerRecordV2",
            "proof-completion reason classes must be nonempty strings",
        )
    # Each input occurrence denotes one blocker record.  Equal reason classes
    # at different schedule coordinates are still multiple blockers and must
    # collapse to OpenModelObligations.
    return tuple(
        make_blocker(
            scope=BlockerScope.PROOF_COMPLETION,
            reason=reason,
            schedule_ordinal=ordinal,
        )
        for ordinal, reason in enumerate(sorted(values))
    )


def default_audit_query() -> dict[str, object]:
    """Return the closed AuditAll query used by synthetic aggregation fixtures."""

    return {
        "queryKind": {"tag": "AuditAll"},
        "entryScope": {"tag": "Some", "value": "entry.main"},
        "coalitionScope": {
            "tag": "ConcreteCoalition",
            "coalitionId": DEFAULT_COALITION_ID,
        },
        "releaseScope": {"tag": "None"},
        "componentScope": {"tag": "None"},
        "relationScope": {"tag": "None"},
    }


def make_accepted_bad_replay(
    *,
    artifact_identity_digest: str = ZERO_DIGEST,
    proof_configuration_digest: str = DEFAULT_PROOF_CONFIGURATION_DIGEST,
    query_schedule_digest: str = DEFAULT_QUERY_SCHEDULE_DIGEST,
    query_ordinal: int = 0,
    query: Mapping[str, object] | None = None,
    first_bad_step: int = 3,
    first_bad_state_digest: str = DEFAULT_FIRST_BAD_STATE_DIGEST,
    receipt_id: str = DEFAULT_PROOF_CONFIGURATION_DIGEST,
) -> AcceptedBadReplayV2:
    """Build a complete identity-bound synthetic replay token."""

    query_value = default_audit_query() if query is None else dict(query)
    return AcceptedBadReplayV2.from_json(
        {
            "formatId": "SPS-Accepted-Bad-Replay-v2",
            "artifactIdentityDigest": artifact_identity_digest,
            "proofConfigurationDigest": proof_configuration_digest,
            "queryScheduleDigest": query_schedule_digest,
            "queryOrdinal": query_ordinal,
            "query": query_value,
            "replaySemantics": "SPS-Replay-Acceptance-v2",
            "firstBadStep": first_bad_step,
            "firstBadStateDigest": first_bad_state_digest,
            "finalReceiptId": receipt_id,
            "protectedEvidence": {
                "receiptId": receipt_id,
                "sensitivity": "SecretBearing",
                "storageClass": "RestrictedVerifierStore",
            },
        }
    )


def make_aggregation_input(
    *,
    accepted_bad_replay: AcceptedBadReplayV2 | None,
    blockers: Iterable[BlockerRecordV2],
    all_required_gates_closed: bool,
    artifact_identity_digest: str = ZERO_DIGEST,
    proof_configuration_digest: str = DEFAULT_PROOF_CONFIGURATION_DIGEST,
    query_schedule_digest: str = DEFAULT_QUERY_SCHEDULE_DIGEST,
) -> AggregationInputV2:
    records = tuple(blockers)
    if any(not isinstance(record, BlockerRecordV2) for record in records):
        raise TypeError("blockers must contain only BlockerRecordV2 values")
    accepted_option: dict[str, object] = (
        {"tag": "None"}
        if accepted_bad_replay is None
        else {"tag": "Some", "value": accepted_bad_replay.as_json()}
    )
    blocker_values = sorted(
        (record.as_json() for record in records),
        key=sps_interfaces.canonical_bytes,
    )
    return AggregationInputV2.from_json(
        {
            "formatId": "SPS-Aggregation-Input-v2",
            "artifactIdentityDigest": artifact_identity_digest,
            "proofConfigurationDigest": proof_configuration_digest,
            "queryScheduleDigest": query_schedule_digest,
            "acceptedBadReplay": accepted_option,
            "blockers": blocker_values,
            "allRequiredGatesClosed": all_required_gates_closed,
        }
    )


def collapse_blockers(blockers: Iterable[BlockerRecordV2]) -> str | None:
    records = tuple(blockers)
    if any(not isinstance(record, BlockerRecordV2) for record in records):
        raise TypeError("collapse_blockers requires BlockerRecordV2 values")
    reasons = [record.reason_class_id for record in records]
    if any(reason is None for reason in reasons):
        raise TypeError("reporting blockers cannot collapse into ModelStatus.Unknown")
    typed_reasons = [reason for reason in reasons if reason is not None]
    if not records:
        return None
    if len(records) == 1:
        return typed_reasons[0]
    return OPEN_MODEL_OBLIGATIONS


def aggregate_model_result(input_value: AggregationInputV2) -> AggregationOutcomeV2:
    """Apply SPS-Model-Aggregation-v2 to one registry-validated input."""

    if not isinstance(input_value, AggregationInputV2):
        raise TypeError("aggregate_model_result requires AggregationInputV2")
    invalidating = tuple(
        blocker
        for blocker in input_value.blockers
        if blocker.scope is BlockerScope.REPLAY_INVALIDATING
    )
    if input_value.accepted_bad_replay is not None and invalidating:
        reasons = sorted(
            reason
            for reason in {blocker.reason_class_id for blocker in invalidating}
            if reason is not None
        )
        raise AggregationInputError(
            ACCEPTED_REPLAY_INVALIDATING_ERROR,
            "accepted bad replay cannot coexist with ReplayInvalidating "
            f"blockers: {reasons}",
        )
    if any(
        blocker.scope is BlockerScope.RUN_FINALIZATION
        for blocker in input_value.blockers
    ):
        return ReportingFailedAggregationV2(input_value.blockers)
    if input_value.accepted_bad_replay is not None:
        status: dict[str, object] = {
            "tag": "Counterexample",
            "args": [input_value.accepted_bad_replay.receipt_id],
        }
    else:
        reason = collapse_blockers(input_value.blockers)
        status = (
            {"tag": "Proved"}
            if reason is None
            else {"tag": "Unknown", "args": [{"reasonClassId": reason}]}
        )
    try:
        _REGISTRY.validate_root(status, "ModelStatusV2")
    except sps_interfaces.InterfaceError as error:
        raise _interface_error("MalformedModelStatusV2", error) from error
    return CompletedAggregationV2(status, input_value.blockers)


def describe(blockers: Iterable[BlockerRecordV2]) -> str:
    records = tuple(blockers)
    reasons = sorted(
        reason for record in records if (reason := record.reason_class_id) is not None
    )
    collapsed = collapse_blockers(records)
    if collapsed is None:
        return "0 blockers -> Proved"
    if len(records) == 1:
        return f"1 blocker {reasons[0]} -> Unknown({reasons[0]})"
    return (
        f"{len(records)} blockers {reasons} -> "
        f"Unknown({OPEN_MODEL_OBLIGATIONS})"
    )


def _example_accepted_replay() -> AcceptedBadReplayV2:
    return make_accepted_bad_replay()


def _self_test() -> None:
    empty = make_aggregation_input(
        accepted_bad_replay=None, blockers=(), all_required_gates_closed=True
    )
    print(describe(empty.blockers))
    one_records = proof_completion_blockers(["SolverTimeout"])
    print(describe(one_records))
    duplicate_source = proof_completion_blockers(["SolverTimeout", "SolverTimeout"])
    print("equal reasons remain separate records: " + describe(duplicate_source))
    exact_duplicate = make_blocker(
        scope=BlockerScope.PROOF_COMPLETION,
        reason="SolverTimeout",
    )
    try:
        make_aggregation_input(
            accepted_bad_replay=None,
            blockers=(exact_duplicate, exact_duplicate),
            all_required_gates_closed=False,
        )
    except AggregationInputError:
        print("exact duplicate blocker records -> rejected")
    else:
        raise SystemExit("exact duplicate blocker records were accepted")
    two_records = proof_completion_blockers(["SolverTimeout", "PossibleUB"])
    print(describe(two_records))

    accepted = _example_accepted_replay()
    accepted_wire = accepted.as_json()
    if (
        accepted_wire["queryScheduleDigest"] != DEFAULT_QUERY_SCHEDULE_DIGEST
        or accepted_wire["queryOrdinal"] != 0
        or accepted_wire["query"] != default_audit_query()
        or accepted_wire["firstBadStateDigest"] != DEFAULT_FIRST_BAD_STATE_DIGEST
    ):
        raise SystemExit(f"accepted replay binding is incomplete: {accepted_wire!r}")
    proof_input = make_aggregation_input(
        accepted_bad_replay=accepted,
        blockers=one_records,
        all_required_gates_closed=False,
    )
    if (
        proof_input.artifact_identity_digest != accepted.artifact_identity_digest
        or proof_input.proof_configuration_digest
        != accepted.proof_configuration_digest
        or proof_input.query_schedule_digest != accepted.query_schedule_digest
    ):
        raise SystemExit("aggregation input did not retain replay identity bindings")
    mismatched_replay = make_accepted_bad_replay(query_schedule_digest="4" * 64)
    try:
        make_aggregation_input(
            accepted_bad_replay=mismatched_replay,
            blockers=one_records,
            all_required_gates_closed=False,
        )
    except AggregationInputError as error:
        if error.code != "XF-REPLAY-002":
            raise
        print("accepted replay with mismatched schedule binding -> rejected (XF-REPLAY-002)")
    else:
        raise SystemExit("mismatched accepted replay schedule binding was accepted")
    counterexample = aggregate_model_result(proof_input)
    if not isinstance(counterexample, CompletedAggregationV2) or counterexample.model_status[
        "tag"
    ] != "Counterexample":
        raise SystemExit(f"counterexample priority broken: {counterexample!r}")
    print("accepted replay outranks ProofCompletion blocker -> Counterexample")

    invalidating = (
        make_blocker(
            scope=BlockerScope.REPLAY_INVALIDATING,
            reason="PONFFPArithmeticUnsupported",
        ),
    )
    invalid_input = make_aggregation_input(
        accepted_bad_replay=accepted,
        blockers=invalidating,
        all_required_gates_closed=False,
    )
    try:
        aggregate_model_result(invalid_input)
    except AggregationInputError as error:
        if error.code != ACCEPTED_REPLAY_INVALIDATING_ERROR:
            raise
        print(f"accepted replay plus ReplayInvalidating blocker -> rejected ({error.code})")
    else:
        raise SystemExit("accepted replay plus ReplayInvalidating blocker was accepted")

    finalization = (
        make_blocker(
            scope=BlockerScope.RUN_FINALIZATION,
            reason="EvidenceFinalizationFailure",
        ),
    )
    reporting_input = make_aggregation_input(
        accepted_bad_replay=accepted,
        blockers=finalization,
        all_required_gates_closed=False,
    )
    reporting = aggregate_model_result(reporting_input)
    if not isinstance(reporting, ReportingFailedAggregationV2) or hasattr(
        reporting, "model_status"
    ):
        raise SystemExit(f"reporting failure leaked ModelStatus: {reporting!r}")
    print(
        "RunFinalization blocker outranks accepted replay -> ReportingFailed; "
        "ModelStatus absent"
    )


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["--self-test"]:
        _self_test()
    else:
        raise SystemExit("usage: sps_aggregation.py --self-test")
