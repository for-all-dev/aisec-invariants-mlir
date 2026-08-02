"""Independent concrete materialization and replay checks."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Mapping

from .canonical import load_json_bytes
from .encoding import encode_bits
from .engine import CompiledProgram, assert_compiled_integrity
from .errors import ReferenceError, ReplayError
from .model import Coalition
from .product import build_product


@dataclass(frozen=True)
class ConcreteEvent:
    kind: str
    site: str
    visit: int
    within_ordinal: int
    value_bytes: tuple[int, ...]
    output_id: str | None
    release_id: str | None
    release_ordinal: int | None
    audience: frozenset[str]
    footprint_bytes: tuple[int, ...]
    observation_hosts: frozenset[str]
    transfer_source: str | None
    transfer_destinations: tuple[str, ...]
    bound_id: str | None
    snapshot_names: tuple[str, ...]


@dataclass(frozen=True)
class ReplayRecord:
    format_id: str
    accepted: bool
    first_bad_event_ordinal: int | None
    bad_cause: str | None
    left_trace: tuple[ConcreteEvent, ...]
    right_trace: tuple[ConcreteEvent, ...]

    def to_obj(self) -> dict[str, Any]:
        return {
            "formatId": self.format_id,
            "accepted": self.accepted,
            "firstBadEventOrdinal": self.first_bad_event_ordinal,
            "badCause": self.bad_cause,
            "leftTrace": [_event_obj(event) for event in self.left_trace],
            "rightTrace": [_event_obj(event) for event in self.right_trace],
        }


@dataclass(frozen=True)
class ConcreteSearchResult:
    status: str
    witness: dict[str, int] | None
    replay: ReplayRecord | None
    detail: str


def replay_witness(
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    witness: Mapping[str, int],
) -> ReplayRecord:
    _validate_replay_context(left, right, coalition, witness)
    return _replay_witness_core(left, right, coalition, witness)


def run_concrete_exhaustive(
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    max_assignments: int = 1_000_000,
) -> ConcreteSearchResult:
    """Search the independently interpreted product over its complete domain."""

    _validate_product_profile(left, right, coalition)
    lane_total = 1
    pair_total = 1
    for item in left.inputs:
        lane_total *= 1 << item.width
        pair_total *= 1 << (
            item.width if item.classification == "Low" else 2 * item.width
        )
    if lane_total > max_assignments or pair_total > max_assignments:
        return ConcreteSearchResult(
            "unknown",
            None,
            None,
            f"lane domain={lane_total}, low-equal pair domain={pair_total}, "
            f"cap={max_assignments}",
        )

    domains = [range(1 << item.width) for item in left.inputs]
    left_traces: dict[tuple[int, ...], tuple[ConcreteEvent, ...]] = {}
    right_traces: dict[tuple[int, ...], tuple[ConcreteEvent, ...]] = {}
    for values in itertools.product(*domains):
        left_environment = {
            f"L.input.{item.input_id}": value
            for item, value in zip(left.inputs, values, strict=True)
        }
        right_environment = {
            f"R.input.{item.input_id}": value
            for item, value in zip(right.inputs, values, strict=True)
        }
        left_traces[values] = _validated_lane_trace(left, left_environment)
        right_traces[values] = _validated_lane_trace(right, right_environment)

    paired_domains: list[range] = []
    for item in left.inputs:
        paired_domains.append(range(1 << item.width))
        if item.classification == "High":
            paired_domains.append(range(1 << item.width))
    for paired_values in itertools.product(*paired_domains):
        cursor = 0
        left_values: list[int] = []
        right_values: list[int] = []
        for item in left.inputs:
            left_value = paired_values[cursor]
            cursor += 1
            if item.classification == "Low":
                right_value = left_value
            else:
                right_value = paired_values[cursor]
                cursor += 1
            left_values.append(left_value)
            right_values.append(right_value)
        replay = _compare_traces(
            left_traces[tuple(left_values)],
            right_traces[tuple(right_values)],
            coalition,
        )
        if replay.accepted:
            witness = {
                **{
                    f"L.input.{item.input_id}": value
                    for item, value in zip(left.inputs, left_values, strict=True)
                },
                **{
                    f"R.input.{item.input_id}": value
                    for item, value in zip(right.inputs, right_values, strict=True)
                },
            }
            return ConcreteSearchResult("sat", witness, replay, "")
    return ConcreteSearchResult("unsat", None, None, "")


def _replay_witness_core(
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    witness: Mapping[str, int],
) -> ReplayRecord:
    left_symbolic = materialize_trace(left, witness)
    right_symbolic = materialize_trace(right, witness)
    left_trace = interpret_trace(left, witness)
    right_trace = interpret_trace(right, witness)
    if left_trace != left_symbolic or right_trace != right_symbolic:
        raise ReplayError(
            "independent concrete replay disagrees with symbolic event construction"
        )
    return _compare_traces(left_trace, right_trace, coalition)


def _compare_traces(
    left_trace: tuple[ConcreteEvent, ...],
    right_trace: tuple[ConcreteEvent, ...],
    coalition: Coalition,
) -> ReplayRecord:
    active = True
    maximum = max(len(left_trace), len(right_trace))
    for ordinal in range(maximum):
        if not active:
            break
        if ordinal >= len(left_trace) or ordinal >= len(right_trace):
            return ReplayRecord(
                "SPS-Reference-Replay-v2",
                True,
                ordinal,
                "EventAlignment",
                left_trace,
                right_trace,
            )
        left_event = left_trace[ordinal]
        right_event = right_trace[ordinal]
        if _structural_key(left_event) != _structural_key(right_event):
            return ReplayRecord(
                "SPS-Reference-Replay-v2",
                True,
                ordinal,
                "SiteOrderAlignment",
                left_trace,
                right_trace,
            )
        payload_differs = left_event.value_bytes != right_event.value_bytes
        if left_event.kind == "Release":
            authorized = bool(left_event.audience & coalition.principals)
            visible = authorized or bool(
                left_event.observation_hosts & coalition.controlled_hosts
            )
            if payload_differs and authorized:
                if left_event.footprint_bytes != tuple(
                    range(len(left_event.value_bytes))
                ):
                    raise ReplayError("partial-footprint release is outside reference slice")
                active = False
            elif payload_differs and visible:
                return ReplayRecord(
                    "SPS-Reference-Replay-v2",
                    True,
                    ordinal,
                    "ProjectedPayloadMismatch",
                    left_trace,
                    right_trace,
                )
        elif payload_differs and _concrete_value_visible(left_event, coalition):
            return ReplayRecord(
                "SPS-Reference-Replay-v2",
                True,
                ordinal,
                "ProjectedPayloadMismatch",
                left_trace,
                right_trace,
            )
    return ReplayRecord(
        "SPS-Reference-Replay-v2",
        False,
        None,
        None,
        left_trace,
        right_trace,
    )


def _validate_program_pair(
    left: CompiledProgram, right: CompiledProgram
) -> None:
    try:
        assert_compiled_integrity(left)
        assert_compiled_integrity(right)
    except ReferenceError as exc:
        raise ReplayError(f"compiled-artifact integrity failure: {exc}") from exc
    if left.lane != "L" or right.lane != "R":
        raise ReplayError("replay requires canonical L and R lanes")
    if left.program_bytes != right.program_bytes or left.inputs != right.inputs:
        raise ReplayError("replay lanes do not bind the same canonical program")


def _validate_replay_context(
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    witness: Mapping[str, int],
) -> None:
    _validate_product_profile(left, right, coalition)
    expected = {
        f"{lane}.input.{item.input_id}": item.width
        for lane in ("L", "R")
        for item in left.inputs
    }
    if set(witness) != set(expected):
        raise ReplayError(
            "witness domain mismatch: "
            f"missing={sorted(set(expected) - set(witness))}, "
            f"extra={sorted(set(witness) - set(expected))}"
        )
    for name, width in expected.items():
        value = witness[name]
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
            or value >= 1 << width
        ):
            raise ReplayError(f"witness value for {name} has wrong width")
    for item in left.inputs:
        if item.classification == "Low" and (
            witness[f"L.input.{item.input_id}"]
            != witness[f"R.input.{item.input_id}"]
        ):
            raise ReplayError(f"witness violates LowEq for {item.input_id}")


def _validate_product_profile(
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
) -> None:
    _validate_program_pair(left, right)
    try:
        build_product(left, right, coalition)
    except ReferenceError as exc:
        raise ReplayError(f"unsupported product/replay profile: {exc}") from exc


def _validated_lane_trace(
    compiled: CompiledProgram, environment: Mapping[str, int]
) -> tuple[ConcreteEvent, ...]:
    symbolic = materialize_trace(compiled, environment)
    concrete = interpret_trace(compiled, environment)
    if symbolic != concrete:
        raise ReplayError(
            "independent concrete replay disagrees with symbolic event construction"
        )
    return concrete


def materialize_trace(
    compiled: CompiledProgram, environment: Mapping[str, int]
) -> tuple[ConcreteEvent, ...]:
    result: list[ConcreteEvent] = []
    for event in compiled.events:
        if not bool(event.present.evaluate(environment)):
            continue
        result.append(
            ConcreteEvent(
                kind=event.kind,
                site=event.site,
                visit=int(event.visit.evaluate(environment)),
                within_ordinal=event.within_ordinal,
                value_bytes=tuple(
                    int(value.evaluate(environment)) for value in event.value_bytes
                ),
                output_id=event.output_id,
                release_id=event.release_id,
                release_ordinal=(
                    None
                    if event.release_ordinal is None
                    else int(event.release_ordinal.evaluate(environment))
                ),
                audience=event.audience,
                footprint_bytes=event.footprint_bytes,
                observation_hosts=event.observation_hosts,
                transfer_source=event.transfer_source,
                transfer_destinations=event.transfer_destinations,
                bound_id=event.bound_id,
                snapshot_names=event.snapshot_names,
            )
        )
    return tuple(result)


@dataclass(frozen=True)
class _ConcreteValue:
    sort: str
    width: int | None
    value: int | bool


class _ConcreteInterpreter:
    """Interpreter independent of the symbolic event expressions."""

    def __init__(
        self, compiled: CompiledProgram, environment: Mapping[str, int]
    ) -> None:
        self.compiled = compiled
        self.program = load_json_bytes(compiled.program_bytes)
        self.environment = environment
        self.variables: dict[str, _ConcreteValue] = {}
        for item in compiled.inputs:
            symbol = f"{compiled.lane}.input.{item.input_id}"
            if symbol not in environment:
                raise ReplayError(f"witness omits {symbol}")
            value = environment[symbol]
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                or value >= 1 << item.width
            ):
                raise ReplayError(f"witness value for {symbol} has wrong width")
            self.variables[item.input_id] = _ConcreteValue("BV", item.width, value)
        self.roots = {
            root["id"]: {
                "bytes": list(root["initialBytes"]),
                "initialized": list(root["initialized"]),
                "host": root["host"],
                "outputId": root["outputId"],
            }
            for root in self.program["abi"]["roots"]
        }
        self.events: list[ConcreteEvent] = []
        self.site_visits: dict[str, int] = {}
        self.release_attempts: dict[str, int] = {}
        self.active = True
        self.terminal = False

    def run(self) -> tuple[ConcreteEvent, ...]:
        self._statements(self.program["statements"])
        return tuple(self.events)

    def _statements(self, statements: list[dict[str, Any]]) -> None:
        for statement in statements:
            if not self.active:
                return
            self._statement(statement)

    def _statement(self, statement: dict[str, Any]) -> None:
        if not self.active:
            return
        op = statement["op"]
        site = statement["site"]
        visit = self.site_visits.get(site, 0)

        if op == "set":
            target = statement["target"]
            value = self._expr(statement["value"])
            current = self.variables.get(target)
            if (
                current is None
                or value.sort != "BV"
                or value.width != current.width
            ):
                raise ReplayError(f"{site}: concrete set sort mismatch")
            self.variables[target] = value
        elif op == "store":
            root = self.roots.get(statement["root"])
            if root is None:
                raise ReplayError(f"{site}: concrete store has unknown root")
            value = self._require_bv(self._expr(statement["value"]), site)
            raw = encode_bits(int(value.value), int(value.width), statement["byteOrder"])
            offset = statement["offset"]
            if offset < 0 or offset + len(raw) > len(root["bytes"]):
                raise ReplayError(f"{site}: concrete store exceeds root")
            for index, byte in enumerate(raw):
                root["bytes"][offset + index] = byte
                root["initialized"][offset + index] = True
        elif op == "if":
            condition = self._require_bool(self._expr(statement["condition"]), site)
            self._append(
                kind="BranchSuccessor",
                site=site,
                visit=visit,
                within_ordinal=0,
                value_bytes=(1 if condition else 0,),
                observation_hosts=frozenset({self.program["entryHost"]}),
            )
            self._statements(statement["then"] if condition else statement["else"])
        elif op == "loop":
            iterations_value = self._require_bv(
                self._expr(statement["iterations"]), site
            )
            iterations = int(iterations_value.value)
            maximum = statement["boundMaximum"]
            for copy_index in range(maximum):
                if copy_index >= iterations or not self.active:
                    break
                self._append(
                    kind="LoopContinuation",
                    site=site,
                    visit=visit,
                    within_ordinal=copy_index,
                    value_bytes=(1,),
                    observation_hosts=frozenset({self.program["entryHost"]}),
                    bound_id=statement["boundId"],
                )
                self._statements(statement["body"])
            if self.active and iterations > maximum:
                self._append(
                    kind="BoundExhausted",
                    site=site,
                    visit=visit,
                    within_ordinal=maximum,
                    observation_hosts=frozenset({self.program["entryHost"]}),
                    bound_id=statement["boundId"],
                )
                self.active = False
                self.terminal = True
        elif op == "releaseAttempt":
            attempt = self.release_attempts.get(statement["releaseId"], 0)
            guard = self._require_bool(self._expr(statement["guard"]), site)
            if guard:
                value = self._require_bv(self._expr(statement["value"]), site)
                raw = encode_bits(int(value.value), int(value.width), "BigEndian")
                self._append(
                    kind="Release",
                    site=site,
                    visit=visit,
                    within_ordinal=0,
                    value_bytes=tuple(raw),
                    release_id=statement["releaseId"],
                    release_ordinal=attempt,
                    audience=frozenset(statement["audience"]),
                    footprint_bytes=tuple(statement["footprintBytes"]),
                    observation_hosts=frozenset({statement["host"]}),
                )
            self.release_attempts[statement["releaseId"]] = attempt + 1
        elif op == "transfer":
            value = self._require_bv(self._expr(statement["value"]), site)
            raw = encode_bits(int(value.value), int(value.width), "BigEndian")
            destinations = tuple(statement["destinationHosts"])
            self._append(
                kind="Transfer",
                site=site,
                visit=visit,
                within_ordinal=0,
                value_bytes=tuple(raw),
                observation_hosts=frozenset(
                    [statement["sourceHost"], *destinations]
                ),
                transfer_source=statement["sourceHost"],
                transfer_destinations=destinations,
            )
        elif op == "return":
            self._return(statement, visit)
        else:
            raise ReplayError(f"{site}: unsupported concrete operation {op}")

        self.site_visits[site] = visit + 1
        if (
            self.program["observerProfile"] == "ArchitecturalStateSnapshots"
            and op != "return"
            and self.active
        ):
            self._snapshot(site, visit)

    def _return(self, statement: dict[str, Any], visit: int) -> None:
        site = statement["site"]
        ordinal = 0
        binding = self.program["abi"]["return"]
        if binding is None:
            if statement["value"] is not None:
                raise ReplayError(f"{site}: concrete void return has a value")
        else:
            value = self._require_bv(self._expr(statement["value"]), site)
            if value.width != binding["width"]:
                raise ReplayError(f"{site}: concrete return width mismatch")
            raw = encode_bits(
                int(value.value), int(value.width), binding["byteOrder"]
            )
            self._append(
                kind="Output",
                site=site,
                visit=visit,
                within_ordinal=ordinal,
                value_bytes=tuple(raw),
                output_id=binding["outputId"],
                observation_hosts=frozenset(
                    {self.program["entryHost"], binding["host"]}
                ),
            )
            ordinal += 1
        for root in self.program["abi"]["roots"]:
            state = self.roots[root["id"]]
            if not all(state["initialized"]):
                raise ReplayError(f"{site}: concrete output contains uninitialized byte")
            self._append(
                kind="Output",
                site=site,
                visit=visit,
                within_ordinal=ordinal,
                value_bytes=tuple(state["bytes"]),
                output_id=root["outputId"],
                observation_hosts=frozenset(
                    {self.program["entryHost"], root["host"]}
                ),
            )
            ordinal += 1
        self._append(
            kind="Termination",
            site=site,
            visit=visit,
            within_ordinal=ordinal,
            observation_hosts=frozenset({self.program["entryHost"]}),
        )
        self.active = False
        self.terminal = True

    def _snapshot(self, site: str, visit: int) -> None:
        by_host: dict[str, list[tuple[str, _ConcreteValue]]] = {}
        input_hosts = {item.input_id: item.host for item in self.compiled.inputs}
        for name, value in self.variables.items():
            by_host.setdefault(input_hosts[name], []).append((f"var:{name}", value))
        for root in self.program["abi"]["roots"]:
            state = self.roots[root["id"]]
            for index, byte in enumerate(state["bytes"]):
                by_host.setdefault(root["host"], []).append(
                    (f"root:{root['id']}:{index}", _ConcreteValue("BV", 8, byte))
                )
        for host in sorted(by_host):
            rows = sorted(by_host[host], key=lambda row: row[0])
            payload: list[int] = []
            names: list[str] = []
            for name, value in rows:
                names.append(name)
                bv = self._require_bv(value, site)
                payload.extend(
                    encode_bits(int(bv.value), int(bv.width), "BigEndian")
                )
            self._append(
                kind="ReferenceArchitecturalStateSnapshot",
                site=f"{site}:snapshot:{host}",
                visit=visit,
                within_ordinal=255,
                value_bytes=tuple(payload),
                observation_hosts=frozenset({host}),
                snapshot_names=tuple(names),
            )

    def _expr(self, expression: Any) -> _ConcreteValue:
        if not isinstance(expression, dict) or len(expression) != 1:
            raise ReplayError("malformed concrete expression")
        op, payload = next(iter(expression.items()))
        if op == "var":
            try:
                return self.variables[payload]
            except (KeyError, TypeError) as exc:
                raise ReplayError(f"unknown concrete variable {payload!r}") from exc
        if op == "const":
            width = payload["width"]
            value = payload["value"]
            return _ConcreteValue("BV", width, value)
        if op == "bool":
            return _ConcreteValue("Bool", None, payload)
        if op == "not":
            value = self._require_bool(self._expr(payload), "not")
            return _ConcreteValue("Bool", None, not value)
        if op in {"eq", "ult", "add", "xor", "and", "or"}:
            left = self._expr(payload[0])
            right = self._expr(payload[1])
            if left.sort != right.sort or left.width != right.width:
                raise ReplayError(f"{op}: concrete operand sort mismatch")
            if op == "eq":
                return _ConcreteValue("Bool", None, left.value == right.value)
            left_bv = self._require_bv(left, op)
            right_bv = self._require_bv(right, op)
            if op == "ult":
                return _ConcreteValue(
                    "Bool", None, int(left_bv.value) < int(right_bv.value)
                )
            width = int(left_bv.width)
            mask = (1 << width) - 1
            if op == "add":
                value = (int(left_bv.value) + int(right_bv.value)) & mask
            elif op == "xor":
                value = int(left_bv.value) ^ int(right_bv.value)
            elif op == "and":
                value = int(left_bv.value) & int(right_bv.value)
            else:
                value = int(left_bv.value) | int(right_bv.value)
            return _ConcreteValue("BV", width, value & mask)
        if op == "extract":
            source = self._require_bv(self._expr(payload["value"]), "extract")
            low = payload["low"]
            width = payload["width"]
            if low < 0 or width <= 0 or low + width > int(source.width):
                raise ReplayError("invalid concrete extraction")
            value = (int(source.value) >> low) & ((1 << width) - 1)
            return _ConcreteValue("BV", width, value)
        raise ReplayError(f"unsupported concrete expression {op!r}")

    @staticmethod
    def _require_bv(value: _ConcreteValue, context: str) -> _ConcreteValue:
        if value.sort != "BV" or value.width is None:
            raise ReplayError(f"{context}: expected concrete bitvector")
        return value

    @staticmethod
    def _require_bool(value: _ConcreteValue, context: str) -> bool:
        if value.sort != "Bool" or not isinstance(value.value, bool):
            raise ReplayError(f"{context}: expected concrete Boolean")
        return value.value

    def _append(
        self,
        *,
        kind: str,
        site: str,
        visit: int,
        within_ordinal: int,
        value_bytes: tuple[int, ...] = (),
        output_id: str | None = None,
        release_id: str | None = None,
        release_ordinal: int | None = None,
        audience: frozenset[str] = frozenset(),
        footprint_bytes: tuple[int, ...] = (),
        observation_hosts: frozenset[str] = frozenset(),
        transfer_source: str | None = None,
        transfer_destinations: tuple[str, ...] = (),
        bound_id: str | None = None,
        snapshot_names: tuple[str, ...] = (),
    ) -> None:
        self.events.append(
            ConcreteEvent(
                kind=kind,
                site=site,
                visit=visit,
                within_ordinal=within_ordinal,
                value_bytes=value_bytes,
                output_id=output_id,
                release_id=release_id,
                release_ordinal=release_ordinal,
                audience=audience,
                footprint_bytes=footprint_bytes,
                observation_hosts=observation_hosts,
                transfer_source=transfer_source,
                transfer_destinations=transfer_destinations,
                bound_id=bound_id,
                snapshot_names=snapshot_names,
            )
        )


def interpret_trace(
    compiled: CompiledProgram, environment: Mapping[str, int]
) -> tuple[ConcreteEvent, ...]:
    return _ConcreteInterpreter(compiled, environment).run()


def _concrete_value_visible(event: ConcreteEvent, coalition: Coalition) -> bool:
    if event.kind in {
        "Output",
        "Transfer",
        "ReferenceArchitecturalStateSnapshot",
    }:
        return bool(event.observation_hosts & coalition.controlled_hosts)
    if event.kind in {"BranchSuccessor", "LoopContinuation"}:
        return True
    return False


def _structural_key(event: ConcreteEvent) -> tuple[Any, ...]:
    return (
        event.kind,
        event.site,
        event.visit,
        event.within_ordinal,
        event.output_id,
        event.release_id,
        event.release_ordinal,
        tuple(sorted(event.audience)),
        event.footprint_bytes,
        event.transfer_source,
        event.transfer_destinations,
        event.bound_id,
        event.snapshot_names,
    )


def _event_obj(event: ConcreteEvent) -> dict[str, Any]:
    return {
        "kind": event.kind,
        "site": event.site,
        "visit": event.visit,
        "withinOrdinal": event.within_ordinal,
        "valueBytes": list(event.value_bytes),
        "outputId": event.output_id,
        "releaseId": event.release_id,
        "releaseOrdinal": event.release_ordinal,
        "audience": sorted(event.audience),
        "footprintBytes": list(event.footprint_bytes),
        "observationHosts": sorted(event.observation_hosts),
        "transferSource": event.transfer_source,
        "transferDestinations": list(event.transfer_destinations),
        "boundId": event.bound_id,
        "snapshotNames": list(event.snapshot_names),
    }
