"""Symbolic execution and event construction for the reference-only IR."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

from .canonical import canonical_bytes, load_json_bytes
from .encoding import encode_term_bytes
from .errors import SchemaError, UninitializedOutputError, UnsupportedError
from .expand import expand_program, width_for
from .model import Coalition, InputDecl, parse_program
from .terms import (
    Term,
    bool_and,
    bool_lit,
    bool_not,
    bv_binary,
    bv_lit,
    bv_ult,
    equal,
    extract,
    ite,
    var,
)


@dataclass(frozen=True)
class ReferenceEvent:
    kind: str
    site: str
    owner_host: str
    observation_hosts: frozenset[str]
    present: Term
    visit: Term
    within_ordinal: int
    value_bytes: tuple[Term, ...] = ()
    output_id: str | None = None
    release_id: str | None = None
    release_ordinal: Term | None = None
    audience: frozenset[str] = frozenset()
    footprint_bytes: tuple[int, ...] = ()
    transfer_source: str | None = None
    transfer_destinations: tuple[str, ...] = ()
    bound_id: str | None = None
    snapshot_names: tuple[str, ...] = ()


@dataclass
class RootState:
    root_id: str
    host: str
    output_id: str
    bytes: list[Term]
    initialized: list[Term]


@dataclass(frozen=True)
class CompiledProgram:
    lane: str
    program: dict[str, Any]
    program_bytes: bytes
    inputs: tuple[InputDecl, ...]
    input_symbols: dict[str, Term]
    variables: dict[str, Term]
    events: tuple[ReferenceEvent, ...]
    expansion: dict[str, Any]
    terminal: Term

    @property
    def symbolic_inputs(self) -> tuple[Term, ...]:
        return tuple(self.input_symbols[item.input_id] for item in self.inputs)


class _Compiler:
    def __init__(self, program: dict[str, Any], lane: str) -> None:
        snapshot = load_json_bytes(canonical_bytes(program))
        self.program = parse_program(snapshot)
        self.program_bytes = canonical_bytes(self.program)
        self.lane = lane
        self.expansion = expand_program(self.program)
        self.ordinal_width = width_for(self.expansion["horizon"])
        self.inputs = tuple(
            InputDecl(item["id"], item["width"], item["classification"], item["host"])
            for item in self.program["inputs"]
        )
        self.input_symbols = {
            item.input_id: var(f"{lane}.input.{item.input_id}", item.width)
            for item in self.inputs
        }
        self.variables = dict(self.input_symbols)
        self.variable_hosts = {item.input_id: item.host for item in self.inputs}
        self.roots: dict[str, RootState] = {}
        for root in self.program["abi"]["roots"]:
            if not all(root["initialized"]):
                raise UninitializedOutputError(
                    f"{root['id']}: the reference slice requires every ABI "
                    "root byte initialized at entry"
                )
            self.roots[root["id"]] = RootState(
                root_id=root["id"],
                host=root["host"],
                output_id=root["outputId"],
                bytes=[bv_lit(8, byte) for byte in root["initialBytes"]],
                initialized=[bool_lit(flag) for flag in root["initialized"]],
            )
        self.events: list[ReferenceEvent] = []
        self.active = bool_lit(True)
        self.terminal = bool_lit(False)
        self.site_visits: dict[str, Term] = {}
        self.release_attempts: dict[str, Term] = {}

    def compile(self) -> CompiledProgram:
        self._statements(self.program["statements"], bool_lit(True))
        return CompiledProgram(
            lane=self.lane,
            program=self.program,
            program_bytes=self.program_bytes,
            inputs=self.inputs,
            input_symbols=dict(self.input_symbols),
            variables=dict(self.variables),
            events=tuple(self.events),
            expansion=self.expansion,
            terminal=self.terminal,
        )

    def _statements(self, statements: list[dict[str, Any]], enclosing: Term) -> None:
        for statement in statements:
            path = bool_and(enclosing, self.active)
            self._statement(statement, path)

    def _statement(self, statement: dict[str, Any], path: Term) -> None:
        op = statement["op"]
        site = statement["site"]
        visit = self.site_visits.setdefault(site, bv_lit(self.ordinal_width, 0))

        if op == "set":
            target = statement["target"]
            if target not in self.variables:
                raise UnsupportedError(
                    f"{site}: reference set requires an existing typed variable"
                )
            value = self._expr(statement["value"])
            if value.sort != "BV" or value.width != self.variables[target].width:
                raise SchemaError(f"{site}: set value sort mismatch")
            self.variables[target] = ite(path, value, self.variables[target])
        elif op == "store":
            self._store(statement, path)
        elif op == "if":
            condition = self._expr(statement["condition"])
            if condition.sort != "Bool":
                raise SchemaError(f"{site}: if condition must be Bool")
            self.events.append(
                ReferenceEvent(
                    kind="BranchSuccessor",
                    site=site,
                    owner_host=self.program["entryHost"],
                    observation_hosts=frozenset({self.program["entryHost"]}),
                    present=path,
                    visit=visit,
                    within_ordinal=0,
                    value_bytes=(ite(condition, bv_lit(8, 1), bv_lit(8, 0)),),
                )
            )
            self._statements(statement["then"], bool_and(path, condition))
            self._statements(statement["else"], bool_and(path, bool_not(condition)))
        elif op == "loop":
            self._loop(statement, path, visit)
        elif op == "releaseAttempt":
            self._release(statement, path, visit)
        elif op == "transfer":
            self._transfer(statement, path, visit)
        elif op == "return":
            self._return(statement, path, visit)
        else:
            raise UnsupportedError(f"{site}: unsupported operation {op}")

        self.site_visits[site] = ite(
            path,
            bv_binary("bvadd", visit, bv_lit(self.ordinal_width, 1)),
            visit,
        )
        if (
            self.program["observerProfile"] == "ArchitecturalStateSnapshots"
            and op != "return"
        ):
            self._snapshot(site, bool_and(path, self.active), visit)

    def _store(self, statement: dict[str, Any], path: Term) -> None:
        site = statement["site"]
        root_id = statement["root"]
        if root_id not in self.roots:
            raise SchemaError(f"{site}: unknown root {root_id}")
        root = self.roots[root_id]
        offset = statement["offset"]
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise SchemaError(f"{site}: store offset must be a natural")
        value = self._expr(statement["value"])
        encoded = encode_term_bytes(value, statement["byteOrder"])
        if offset + len(encoded) > len(root.bytes):
            raise SchemaError(f"{site}: store exceeds root")
        for index, byte in enumerate(encoded):
            target = offset + index
            root.bytes[target] = ite(path, byte, root.bytes[target])
            root.initialized[target] = ite(path, bool_lit(True), root.initialized[target])

    def _loop(self, statement: dict[str, Any], path: Term, visit: Term) -> None:
        iterations = self._expr(statement["iterations"])
        if iterations.sort != "BV":
            raise SchemaError(f"{statement['site']}: iterations must be a bitvector")
        referenced = collect_expr_variables(statement["iterations"])
        classifications = {item.input_id: item.classification for item in self.inputs}
        if any(classifications.get(name) != "Low" for name in referenced):
            raise UnsupportedError(
                f"{statement['site']}: reference loop iterations must be Low"
            )
        maximum = statement["boundMaximum"]
        for copy_index in range(maximum):
            if copy_index >= 1 << int(iterations.width):
                copy_guard = bool_lit(False)
            else:
                copy_guard = bv_ult(
                    bv_lit(int(iterations.width), copy_index), iterations
                )
            active_copy = bool_and(path, copy_guard, self.active)
            self.events.append(
                ReferenceEvent(
                    kind="LoopContinuation",
                    site=statement["site"],
                    owner_host=self.program["entryHost"],
                    observation_hosts=frozenset({self.program["entryHost"]}),
                    present=active_copy,
                    visit=visit,
                    within_ordinal=copy_index,
                    value_bytes=(bv_lit(8, 1),),
                    bound_id=statement["boundId"],
                )
            )
            self._statements(statement["body"], active_copy)
        if maximum >= 1 << int(iterations.width):
            remainder_guard = bool_lit(False)
        else:
            remainder_guard = bv_ult(
                bv_lit(int(iterations.width), maximum), iterations
            )
        remainder_present = bool_and(path, remainder_guard, self.active)
        self.events.append(
            ReferenceEvent(
                kind="BoundExhausted",
                site=statement["site"],
                owner_host=self.program["entryHost"],
                observation_hosts=frozenset({self.program["entryHost"]}),
                present=remainder_present,
                visit=visit,
                within_ordinal=maximum,
                bound_id=statement["boundId"],
            )
        )
        self.terminal = ite(remainder_present, bool_lit(True), self.terminal)
        self.active = bool_and(self.active, bool_not(remainder_present))

    def _release(self, statement: dict[str, Any], path: Term, visit: Term) -> None:
        release_id = statement["releaseId"]
        attempt = self.release_attempts.setdefault(
            release_id, bv_lit(self.ordinal_width, 0)
        )
        guard = self._expr(statement["guard"])
        if guard.sort != "Bool":
            raise SchemaError(f"{statement['site']}: release guard must be Bool")
        value = self._expr(statement["value"])
        encoded = tuple(encode_term_bytes(value, "BigEndian"))
        raw_footprint = statement["footprintBytes"]
        if not isinstance(raw_footprint, list):
            raise SchemaError(f"{statement['site']}: invalid release footprint")
        footprint = tuple(raw_footprint)
        if (
            not footprint
            or any(
                not isinstance(index, int)
                or isinstance(index, bool)
                or index < 0
                or index >= len(encoded)
                for index in footprint
            )
            or list(footprint) != sorted(set(footprint))
        ):
            raise SchemaError(f"{statement['site']}: invalid release footprint")
        audience = statement["audience"]
        if not isinstance(audience, list) or len(audience) != len(set(audience)):
            raise SchemaError(f"{statement['site']}: invalid audience")
        self.events.append(
            ReferenceEvent(
                kind="Release",
                site=statement["site"],
                owner_host=statement["host"],
                observation_hosts=frozenset({statement["host"]}),
                present=bool_and(path, guard),
                visit=visit,
                within_ordinal=0,
                value_bytes=encoded,
                release_id=release_id,
                release_ordinal=attempt,
                audience=frozenset(audience),
                footprint_bytes=footprint,
            )
        )
        self.release_attempts[release_id] = ite(
            path,
            bv_binary("bvadd", attempt, bv_lit(self.ordinal_width, 1)),
            attempt,
        )

    def _transfer(self, statement: dict[str, Any], path: Term, visit: Term) -> None:
        value = self._expr(statement["value"])
        destinations = statement["destinationHosts"]
        if not isinstance(destinations, list) or len(destinations) != len(
            set(destinations)
        ):
            raise SchemaError(f"{statement['site']}: invalid destinations")
        hosts = frozenset([statement["sourceHost"], *destinations])
        self.events.append(
            ReferenceEvent(
                kind="Transfer",
                site=statement["site"],
                owner_host=statement["sourceHost"],
                observation_hosts=hosts,
                present=path,
                visit=visit,
                within_ordinal=0,
                value_bytes=tuple(encode_term_bytes(value, "BigEndian")),
                transfer_source=statement["sourceHost"],
                transfer_destinations=tuple(destinations),
            )
        )

    def _return(self, statement: dict[str, Any], path: Term, visit: Term) -> None:
        ordinal = 0
        return_binding = self.program["abi"]["return"]
        if return_binding is None:
            if statement["value"] is not None:
                raise SchemaError(f"{statement['site']}: void return has a value")
        else:
            value = self._expr(statement["value"])
            if value.sort != "BV" or value.width != return_binding["width"]:
                raise SchemaError(f"{statement['site']}: return value sort mismatch")
            self.events.append(
                ReferenceEvent(
                    kind="Output",
                    site=statement["site"],
                    owner_host=self.program["entryHost"],
                    observation_hosts=frozenset(
                        {self.program["entryHost"], return_binding["host"]}
                    ),
                    present=path,
                    visit=visit,
                    within_ordinal=ordinal,
                    value_bytes=tuple(
                        encode_term_bytes(value, return_binding["byteOrder"])
                    ),
                    output_id=return_binding["outputId"],
                )
            )
            ordinal += 1
        for root in self.roots.values():
            for index, initialized in enumerate(root.initialized):
                if initialized.op == "bool" and initialized.value is False:
                    raise UninitializedOutputError(
                        f"{statement['site']}: root {root.root_id}[{index}] is uninitialized"
                    )
            self.events.append(
                ReferenceEvent(
                    kind="Output",
                    site=statement["site"],
                    owner_host=self.program["entryHost"],
                    observation_hosts=frozenset(
                        {self.program["entryHost"], root.host}
                    ),
                    present=path,
                    visit=visit,
                    within_ordinal=ordinal,
                    value_bytes=tuple(root.bytes),
                    output_id=root.output_id,
                )
            )
            ordinal += 1
        self.events.append(
            ReferenceEvent(
                kind="Termination",
                site=statement["site"],
                owner_host=self.program["entryHost"],
                observation_hosts=frozenset({self.program["entryHost"]}),
                present=path,
                visit=visit,
                within_ordinal=ordinal,
            )
        )
        self.terminal = ite(path, bool_lit(True), self.terminal)
        self.active = bool_and(self.active, bool_not(path))

    def _snapshot(self, site: str, path: Term, visit: Term) -> None:
        by_host: dict[str, list[tuple[str, Term]]] = {}
        for name, value in self.variables.items():
            by_host.setdefault(self.variable_hosts[name], []).append((f"var:{name}", value))
        for root in self.roots.values():
            for index, value in enumerate(root.bytes):
                by_host.setdefault(root.host, []).append(
                    (f"root:{root.root_id}:{index}", value)
                )
        for host in sorted(by_host):
            rows = sorted(by_host[host], key=lambda row: row[0])
            payload: list[Term] = []
            names: list[str] = []
            for name, value in rows:
                names.append(name)
                payload.extend(encode_term_bytes(value, "BigEndian"))
            self.events.append(
                ReferenceEvent(
                    kind="ReferenceArchitecturalStateSnapshot",
                    site=f"{site}:snapshot:{host}",
                    owner_host=host,
                    observation_hosts=frozenset({host}),
                    present=path,
                    visit=visit,
                    within_ordinal=255,
                    value_bytes=tuple(payload),
                    snapshot_names=tuple(names),
                )
            )

    def _expr(self, value: Any) -> Term:
        if not isinstance(value, dict) or len(value) != 1:
            raise SchemaError("expression must be a one-constructor object")
        key, payload = next(iter(value.items()))
        if key == "var":
            if payload not in self.variables:
                raise SchemaError(f"unknown expression variable {payload!r}")
            return self.variables[payload]
        if key == "const":
            if (
                not isinstance(payload, dict)
                or set(payload) != {"width", "value"}
                or not isinstance(payload["width"], int)
                or isinstance(payload["width"], bool)
                or not isinstance(payload["value"], int)
                or isinstance(payload["value"], bool)
                or payload["width"] <= 0
                or payload["value"] < 0
                or payload["value"] >= 1 << payload["width"]
            ):
                raise SchemaError("invalid const expression")
            return bv_lit(payload["width"], payload["value"])
        if key == "bool":
            if not isinstance(payload, bool):
                raise SchemaError("invalid Boolean literal")
            return bool_lit(payload)
        if key == "not":
            child = self._expr(payload)
            if child.sort != "Bool":
                raise SchemaError("not operand must be Bool")
            return bool_not(child)
        if key in {"eq", "ult", "add", "xor", "and", "or"}:
            if not isinstance(payload, list) or len(payload) != 2:
                raise SchemaError(f"{key} expects two operands")
            left, right = (self._expr(item) for item in payload)
            if key == "eq":
                return equal(left, right)
            if key == "ult":
                return bv_ult(left, right)
            return bv_binary(
                {"add": "bvadd", "xor": "bvxor", "and": "bvand", "or": "bvor"}[key],
                left,
                right,
            )
        if key == "extract":
            if not isinstance(payload, dict) or set(payload) != {"value", "low", "width"}:
                raise SchemaError("invalid extract expression")
            return extract(self._expr(payload["value"]), payload["low"], payload["width"])
        raise SchemaError(f"unsupported expression constructor {key!r}")


def compile_program(program: dict[str, Any], lane: str) -> CompiledProgram:
    if lane not in {"L", "R"}:
        raise SchemaError("lane must be L or R")
    compiled = _Compiler(program, lane).compile()
    require_total_termination(compiled)
    return compiled


def require_total_termination(
    compiled: CompiledProgram, max_assignments: int = 1_000_000
) -> None:
    """Fail closed unless every reference input reaches a terminal transition."""

    declarations = [(item.input_id, item.width) for item in compiled.inputs]
    total = 1
    for _, width in declarations:
        total *= 1 << width
    if total > max_assignments:
        raise UnsupportedError(
            f"{compiled.lane}: total-termination domain {total} exceeds "
            f"reference cap {max_assignments}"
        )
    domains = [range(1 << width) for _, width in declarations]
    for values in itertools.product(*domains):
        environment = {
            f"{compiled.lane}.input.{name}": value
            for (name, _), value in zip(declarations, values, strict=True)
        }
        if not bool(compiled.terminal.evaluate(environment)):
            raise UnsupportedError(
                f"{compiled.lane}: reference program is not terminal for "
                f"{environment}"
            )


def assert_compiled_integrity(compiled: CompiledProgram) -> None:
    """Reject mutation or drift from the canonical compilation snapshot."""

    if canonical_bytes(compiled.program) != compiled.program_bytes:
        raise SchemaError("compiled program was mutated after canonical snapshot")
    snapshot = load_json_bytes(compiled.program_bytes)
    expected = _Compiler(snapshot, compiled.lane).compile()
    if compiled != expected:
        raise SchemaError("compiled artifact disagrees with canonical recompilation")
    require_total_termination(expected)


def collect_expr_variables(value: Any) -> set[str]:
    if isinstance(value, dict):
        if set(value) == {"var"} and isinstance(value["var"], str):
            return {value["var"]}
        result: set[str] = set()
        for child in value.values():
            result.update(collect_expr_variables(child))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for child in value:
            result.update(collect_expr_variables(child))
        return result
    return set()


def event_value_visible(event: ReferenceEvent, coalition: Coalition) -> bool:
    location_visible = bool(event.observation_hosts & coalition.controlled_hosts)
    if event.kind == "Release":
        return bool(event.audience & coalition.principals) or location_visible
    if event.kind in {
        "Transfer",
        "Output",
        "ReferenceArchitecturalStateSnapshot",
    }:
        return location_visible
    return False
