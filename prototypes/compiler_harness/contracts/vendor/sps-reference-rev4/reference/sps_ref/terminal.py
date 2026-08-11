"""Independent symbolic construction of the reduced terminal-output surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .encoding import encode_term_bytes
from .engine import CompiledProgram, ReferenceEvent
from .errors import SchemaError
from .expand import expand_program, width_for
from .terms import (
    Term,
    bool_and,
    bool_lit,
    bool_not,
    bool_or,
    bool_xor,
    bv_binary,
    bv_lit,
    bv_ult,
    equal,
    extract,
    ite,
)


@dataclass(frozen=True)
class TerminalExpectation:
    kind: str
    site: str
    owner_host: str
    observation_hosts: frozenset[str]
    present: Term
    visit: Term
    within_ordinal: int
    value_bytes: tuple[Term, ...] = ()
    output_id: str | None = None
    output_initialized: tuple[Term, ...] = ()
    bound_id: str | None = None


@dataclass
class _RootExpectation:
    host: str
    terminal_output: bool
    output_id: str | None
    bytes: list[Term]
    initialized: list[Term]


class _TerminalExpectationBuilder:
    """Symbolically derive terminal events without using engine event output."""

    def __init__(self, compiled: CompiledProgram) -> None:
        self.program = compiled.program
        self.variables = dict(compiled.input_symbols)
        self.variable_initialized = {
            item.input_id: bool_lit(True) for item in compiled.inputs
        }
        self.roots = {
            root["id"]: _RootExpectation(
                host=root["host"],
                terminal_output=root["terminalOutput"],
                output_id=root["outputId"],
                bytes=[bv_lit(8, byte) for byte in root["initialBytes"]],
                initialized=[bool_lit(flag) for flag in root["initialized"]],
            )
            for root in self.program["abi"]["roots"]
        }
        self.admission = self._expr(self.program["admission"])
        if self.admission.sort != "Bool":
            raise SchemaError("terminal expectation admission must be Boolean")
        expansion = expand_program(self.program)
        self.ordinal_width = width_for(expansion["horizon"])
        self.active = bool_lit(True)
        self.site_visits: dict[str, Term] = {}
        self.events: list[TerminalExpectation] = []

    def build(self) -> tuple[TerminalExpectation, ...]:
        self._statements(self.program["statements"], self.admission)
        return tuple(self.events)

    def _statements(self, statements: list[dict[str, Any]], enclosing: Term) -> None:
        for statement in statements:
            path = bool_and(enclosing, self.active)
            self._statement(statement, path)

    def _statement(self, statement: dict[str, Any], path: Term) -> None:
        op = statement["op"]
        site = statement["site"]
        visit = self.site_visits.setdefault(site, bv_lit(self.ordinal_width, 0))
        if op == "set":
            value = self._expr(statement["value"])
            current = self.variables[statement["target"]]
            if value.sort != "BV" or value.width != current.width:
                raise SchemaError(f"{site}: terminal expectation set mismatch")
            self.variables[statement["target"]] = ite(path, value, current)
            initialized = self._expr_initialized(statement["value"])
            self.variable_initialized[statement["target"]] = ite(
                path,
                initialized,
                self.variable_initialized[statement["target"]],
            )
        elif op == "store":
            self._store(statement, path)
        elif op == "if":
            condition = self._expr(statement["condition"])
            if condition.sort != "Bool":
                raise SchemaError(f"{site}: terminal expectation condition mismatch")
            self._statements(statement["then"], bool_and(path, condition))
            self._statements(
                statement["else"], bool_and(path, bool_not(condition))
            )
        elif op == "loop":
            self._loop(statement, path, visit)
        elif op in {"releaseAttempt", "transfer"}:
            pass
        elif op == "return":
            self._return(statement, path, visit)
        else:
            raise SchemaError(f"{site}: unsupported terminal expectation operation")

        self.site_visits[site] = ite(
            path,
            bv_binary("bvadd", visit, bv_lit(self.ordinal_width, 1)),
            visit,
        )

    def _store(self, statement: dict[str, Any], path: Term) -> None:
        root = self.roots[statement["root"]]
        value = self._expr(statement["value"])
        initialized = self._expr_initialized(statement["value"])
        encoded = encode_term_bytes(value, statement["byteOrder"])
        offset = statement["offset"]
        if offset + len(encoded) > len(root.bytes):
            raise SchemaError(f"{statement['site']}: terminal expectation store exceeds root")
        for index, byte in enumerate(encoded):
            target = offset + index
            root.bytes[target] = ite(path, byte, root.bytes[target])
            root.initialized[target] = ite(
                path, initialized, root.initialized[target]
            )

    def _loop(
        self, statement: dict[str, Any], path: Term, visit: Term
    ) -> None:
        iterations = self._expr(statement["iterations"])
        if iterations.sort != "BV" or iterations.width is None:
            raise SchemaError(
                f"{statement['site']}: terminal expectation iterations mismatch"
            )
        maximum = statement["boundMaximum"]
        for copy_index in range(maximum):
            guard = (
                bool_lit(False)
                if copy_index >= 1 << iterations.width
                else bv_ult(bv_lit(iterations.width, copy_index), iterations)
            )
            self._statements(
                statement["body"], bool_and(path, guard, self.active)
            )
        remainder_guard = (
            bool_lit(False)
            if maximum >= 1 << iterations.width
            else bv_ult(bv_lit(iterations.width, maximum), iterations)
        )
        present = bool_and(path, remainder_guard, self.active)
        self.events.append(
            TerminalExpectation(
                kind="BoundExhausted",
                site=statement["site"],
                owner_host=self.program["entryHost"],
                observation_hosts=frozenset({self.program["entryHost"]}),
                present=present,
                visit=visit,
                within_ordinal=maximum,
                bound_id=statement["boundId"],
            )
        )
        self.active = bool_and(self.active, bool_not(present))

    def _return(
        self, statement: dict[str, Any], path: Term, visit: Term
    ) -> None:
        binding = self.program["abi"]["return"]
        output_sources: dict[
            str, tuple[str, tuple[Term, ...], tuple[Term, ...]]
        ] = {}
        if binding is None:
            if statement["value"] is not None:
                raise SchemaError(
                    f"{statement['site']}: terminal expectation void mismatch"
                )
        else:
            value = self._expr(statement["value"])
            if value.sort != "BV" or value.width != binding["width"]:
                raise SchemaError(
                    f"{statement['site']}: terminal expectation return mismatch"
                )
            encoded = tuple(encode_term_bytes(value, binding["byteOrder"]))
            initialized = self._expr_initialized(statement["value"])
            output_sources[binding["outputId"]] = (
                binding["host"],
                encoded,
                tuple(initialized for _ in encoded),
            )
        for root in self.roots.values():
            if not root.terminal_output:
                continue
            assert root.output_id is not None
            output_sources[root.output_id] = (
                root.host,
                tuple(root.bytes),
                tuple(root.initialized),
            )
        order = self.program["abi"]["terminalOutputOrder"]
        for ordinal, output_id in enumerate(order):
            host, value_bytes, initialized = output_sources[output_id]
            self.events.append(
                TerminalExpectation(
                    kind="Output",
                    site=statement["site"],
                    owner_host=self.program["entryHost"],
                    observation_hosts=frozenset(
                        {self.program["entryHost"], host}
                    ),
                    present=path,
                    visit=visit,
                    within_ordinal=ordinal,
                    value_bytes=value_bytes,
                    output_id=output_id,
                    output_initialized=initialized,
                )
            )
        self.events.append(
            TerminalExpectation(
                kind="Termination",
                site=statement["site"],
                owner_host=self.program["entryHost"],
                observation_hosts=frozenset({self.program["entryHost"]}),
                present=path,
                visit=visit,
                within_ordinal=len(order),
            )
        )
        self.active = bool_and(self.active, bool_not(path))

    def _expr(self, value: Any) -> Term:
        if not isinstance(value, dict) or len(value) != 1:
            raise SchemaError("terminal expectation expression is malformed")
        op, payload = next(iter(value.items()))
        if op == "var":
            try:
                return self.variables[payload]
            except (KeyError, TypeError) as exc:
                raise SchemaError(
                    f"terminal expectation unknown variable {payload!r}"
                ) from exc
        if op == "const":
            return bv_lit(payload["width"], payload["value"])
        if op == "bool":
            return bool_lit(payload)
        if op == "not":
            return bool_not(self._expr(payload))
        if op in {"eq", "ult", "add", "xor", "and", "or"}:
            left, right = (self._expr(item) for item in payload)
            if op == "eq":
                return equal(left, right)
            if op == "ult":
                return bv_ult(left, right)
            return bv_binary(
                {
                    "add": "bvadd",
                    "xor": "bvxor",
                    "and": "bvand",
                    "or": "bvor",
                }[op],
                left,
                right,
            )
        if op == "extract":
            return extract(
                self._expr(payload["value"]), payload["low"], payload["width"]
            )
        if op == "load":
            root = self.roots[payload["root"]]
            byte_width = payload["width"] // 8
            offset = payload["offset"]
            raw = root.bytes[offset : offset + byte_width]
            if len(raw) != byte_width:
                raise SchemaError("terminal expectation load exceeds root")
            significance = (
                raw
                if payload["byteOrder"] == "BigEndian"
                else list(reversed(raw))
            )
            if len(significance) == 1:
                return significance[0]
            return Term("BV", payload["width"], "concat", tuple(significance))
        raise SchemaError(f"unsupported terminal expectation expression {op!r}")

    def _expr_initialized(self, value: Any) -> Term:
        if not isinstance(value, dict) or len(value) != 1:
            raise SchemaError("terminal expectation expression is malformed")
        op, payload = next(iter(value.items()))
        if op == "var":
            return self.variable_initialized[payload]
        if op in {"const", "bool"}:
            return bool_lit(True)
        if op == "load":
            root = self.roots[payload["root"]]
            byte_width = payload["width"] // 8
            offset = payload["offset"]
            initialized = root.initialized[offset : offset + byte_width]
            if len(initialized) != byte_width:
                raise SchemaError("terminal expectation load exceeds root")
            return bool_and(*initialized)
        if op in {"not", "extract"}:
            child = payload if op == "not" else payload["value"]
            return self._expr_initialized(child)
        if op in {"eq", "ult", "add", "xor", "and", "or"}:
            return bool_and(
                *(self._expr_initialized(item) for item in payload)
            )
        raise SchemaError(f"unsupported terminal expectation expression {op!r}")


def symbolic_terminal_surface_violation(compiled: CompiledProgram) -> Term:
    """Compare engine terminal events to an independently derived symbolic surface."""

    expected = _TerminalExpectationBuilder(compiled).build()
    actual = tuple(
        event
        for event in compiled.events
        if event.kind in {"Output", "Termination", "BoundExhausted"}
    )
    if len(actual) != len(expected):
        return bool_lit(True)
    causes: list[Term] = []
    for actual_event, expected_event in zip(actual, expected, strict=True):
        causes.append(bool_xor(actual_event.present, expected_event.present))
        both = bool_and(actual_event.present, expected_event.present)
        static_mismatch = _terminal_static_mismatch(actual_event, expected_event)
        if static_mismatch:
            causes.append(bool_and(both, bool_lit(True)))
        causes.append(
            bool_and(
                both,
                bool_not(equal(actual_event.visit, expected_event.visit)),
            )
        )
        if len(actual_event.value_bytes) != len(expected_event.value_bytes):
            causes.append(bool_and(both, bool_lit(True)))
        else:
            causes.extend(
                bool_and(both, bool_not(equal(actual_byte, expected_byte)))
                for actual_byte, expected_byte in zip(
                    actual_event.value_bytes,
                    expected_event.value_bytes,
                    strict=True,
                )
            )
        if len(actual_event.output_initialized) != len(
            expected_event.output_initialized
        ):
            causes.append(bool_and(both, bool_lit(True)))
        else:
            causes.extend(
                bool_and(both, bool_not(equal(actual_init, expected_init)))
                for actual_init, expected_init in zip(
                    actual_event.output_initialized,
                    expected_event.output_initialized,
                    strict=True,
                )
            )
        if expected_event.kind == "Output":
            causes.append(
                bool_and(
                    both,
                    bool_not(bool_and(*expected_event.output_initialized)),
                )
            )
            causes.append(
                bool_and(
                    both,
                    bool_not(bool_and(*actual_event.output_initialized)),
                )
            )
    return bool_or(*causes)


def _terminal_static_mismatch(
    actual: ReferenceEvent, expected: TerminalExpectation
) -> bool:
    return any(
        (
            actual.kind != expected.kind,
            actual.site != expected.site,
            actual.owner_host != expected.owner_host,
            actual.observation_hosts != expected.observation_hosts,
            actual.within_ordinal != expected.within_ordinal,
            actual.output_id != expected.output_id,
            actual.bound_id != expected.bound_id,
        )
    )
