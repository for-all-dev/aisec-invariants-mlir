"""Reduced reference queries cited by, but distinct from, normative SPS queries."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Mapping

from .engine import (
    CompiledProgram,
    assert_compiled_integrity,
)
from .errors import SchemaError
from .model import Coalition
from .product import BadCause, ReferenceProduct, build_product
from .replay import (
    ConcreteSearchResult,
    concrete_admitted,
    concrete_terminal_surface_violation,
    run_concrete_exhaustive,
)
from .solve import SolverResult
from .terminal import symbolic_terminal_surface_violation
from .terms import Term, bool_and, bool_not, equal


QUERY_KINDS = (
    "ReferenceAdmissionNonempty",
    "ReferenceHighVariation",
    "ReferenceTerminalOutputSurface",
    "ReferenceAuditAll",
)


@dataclass(frozen=True)
class ReferenceQuery:
    query_kind: str
    component_id: str | None
    input_variables: tuple[tuple[str, int], ...]
    initial_constraints: tuple[Term, ...]
    goal: Term
    bad_causes: tuple[BadCause, ...] = ()


def build_reference_query(
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    query_kind: str,
    component_id: str | None = None,
) -> ReferenceQuery:
    assert_compiled_integrity(left)
    assert_compiled_integrity(right)
    if left.program_bytes != right.program_bytes:
        raise SchemaError("reference query lanes must use one canonical program")
    if query_kind not in QUERY_KINDS:
        raise SchemaError(f"unknown reference query kind {query_kind!r}")

    if query_kind == "ReferenceAuditAll":
        _require_no_component(query_kind, component_id)
        product = build_product(left, right, coalition)
        return ReferenceQuery(
            query_kind,
            None,
            product.input_variables,
            (left.admission, right.admission, *product.low_constraints),
            product.bad,
            product.bad_causes,
        )
    if query_kind == "ReferenceAdmissionNonempty":
        _require_no_component(query_kind, component_id)
        return ReferenceQuery(
            query_kind,
            None,
            _lane_variables(left),
            (),
            left.admission,
        )
    if query_kind == "ReferenceHighVariation":
        if component_id is None:
            raise SchemaError("ReferenceHighVariation requires a componentId")
        decl = next(
            (item for item in left.inputs if item.input_id == component_id), None
        )
        if decl is None or decl.classification != "High":
            raise SchemaError(
                "ReferenceHighVariation component must name one High input"
            )
        product = build_product(left, right, coalition)
        return ReferenceQuery(
            query_kind,
            component_id,
            product.input_variables,
            (left.admission, right.admission, *product.low_constraints),
            bool_not(
                equal(
                    left.input_symbols[component_id],
                    right.input_symbols[component_id],
                )
            ),
        )
    _require_no_component(query_kind, component_id)
    return ReferenceQuery(
        query_kind,
        None,
        _lane_variables(left),
        (left.admission,),
        terminal_output_surface_violation(left),
    )


def terminal_output_surface_violation(compiled: CompiledProgram) -> Term:
    """Build a symbolic mismatch against an independent terminal-state builder."""

    return symbolic_terminal_surface_violation(compiled)


def run_query_exhaustive(
    query: ReferenceQuery, max_assignments: int = 1_000_000
) -> SolverResult:
    total = 1
    for _, width in query.input_variables:
        total *= 1 << width
    if total > max_assignments:
        return SolverResult(
            "symbolic-exhaustive",
            "unknown",
            None,
            f"domain has {total} assignments, cap is {max_assignments}",
        )
    domains = [range(1 << width) for _, width in query.input_variables]
    for values in itertools.product(*domains):
        environment = {
            name: value
            for (name, _), value in zip(query.input_variables, values, strict=True)
        }
        if all(
            bool(constraint.evaluate(environment))
            for constraint in query.initial_constraints
        ) and bool(query.goal.evaluate(environment)):
            return SolverResult(
                "symbolic-exhaustive", "sat", environment, ""
            )
    return SolverResult("symbolic-exhaustive", "unsat", None, "")


def run_concrete_query(
    query: ReferenceQuery,
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    max_assignments: int = 1_000_000,
) -> ConcreteSearchResult:
    if query.query_kind == "ReferenceAuditAll":
        return run_concrete_exhaustive(
            left, right, coalition, max_assignments=max_assignments
        )
    if query.query_kind == "ReferenceAdmissionNonempty":
        for environment in _lane_environments(left, max_assignments):
            if concrete_admitted(left, environment):
                return ConcreteSearchResult("sat", dict(environment), None, "")
        return ConcreteSearchResult("unsat", None, None, "")
    if query.query_kind == "ReferenceTerminalOutputSurface":
        for environment in _lane_environments(left, max_assignments):
            if concrete_terminal_surface_violation(left, environment):
                return ConcreteSearchResult("sat", dict(environment), None, "")
        return ConcreteSearchResult("unsat", None, None, "")
    assert query.component_id is not None
    for environment in _pair_environments(left, max_assignments):
        if not concrete_admitted(left, environment) or not concrete_admitted(
            right, environment
        ):
            continue
        if all(
            environment[f"L.input.{item.input_id}"]
            == environment[f"R.input.{item.input_id}"]
            for item in left.inputs
            if item.classification == "Low"
        ) and (
            environment[f"L.input.{query.component_id}"]
            != environment[f"R.input.{query.component_id}"]
        ):
            return ConcreteSearchResult("sat", dict(environment), None, "")
    return ConcreteSearchResult("unsat", None, None, "")


def validate_query_witness(
    query: ReferenceQuery,
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    witness: Mapping[str, int],
) -> bool:
    """Validate a SAT assignment through the independent concrete route."""

    expected = dict(query.input_variables)
    if set(witness) != set(expected):
        return False
    if any(
        not isinstance(witness[name], int)
        or isinstance(witness[name], bool)
        or witness[name] < 0
        or witness[name] >= 1 << width
        for name, width in expected.items()
    ):
        return False
    if query.query_kind == "ReferenceAdmissionNonempty":
        return concrete_admitted(left, witness)
    if query.query_kind == "ReferenceTerminalOutputSurface":
        return concrete_terminal_surface_violation(left, witness)
    if query.query_kind == "ReferenceHighVariation":
        assert query.component_id is not None
        return (
            concrete_admitted(left, witness)
            and concrete_admitted(right, witness)
            and all(
                witness[f"L.input.{item.input_id}"]
                == witness[f"R.input.{item.input_id}"]
                for item in left.inputs
                if item.classification == "Low"
            )
            and witness[f"L.input.{query.component_id}"]
            != witness[f"R.input.{query.component_id}"]
        )
    concrete = run_concrete_exhaustive(left, right, coalition)
    # Direct replay of the candidate, not merely existence, is done by callers for
    # AuditAll. This fallback only protects accidental use of this helper.
    return concrete.status == "sat"


def _lane_variables(compiled: CompiledProgram) -> tuple[tuple[str, int], ...]:
    return tuple(
        (f"{compiled.lane}.input.{item.input_id}", item.width)
        for item in compiled.inputs
    )


def _lane_environments(compiled: CompiledProgram, cap: int):
    declarations = _lane_variables(compiled)
    total = 1
    for _, width in declarations:
        total *= 1 << width
    if total > cap:
        raise SchemaError(f"reference concrete lane domain {total} exceeds cap {cap}")
    domains = [range(1 << width) for _, width in declarations]
    for values in itertools.product(*domains):
        yield {
            name: value
            for (name, _), value in zip(declarations, values, strict=True)
        }


def _pair_environments(compiled: CompiledProgram, cap: int):
    declarations = tuple(
        (f"{lane}.input.{item.input_id}", item.width)
        for lane in ("L", "R")
        for item in compiled.inputs
    )
    total = 1
    for _, width in declarations:
        total *= 1 << width
    if total > cap:
        raise SchemaError(f"reference concrete pair domain {total} exceeds cap {cap}")
    domains = [range(1 << width) for _, width in declarations]
    for values in itertools.product(*domains):
        yield {
            name: value
            for (name, _), value in zip(declarations, values, strict=True)
        }


def _require_no_component(query_kind: str, component_id: str | None) -> None:
    if component_id is not None:
        raise SchemaError(f"{query_kind} forbids componentId")


def product_for_audit_query(query: ReferenceQuery) -> ReferenceProduct:
    """Compatibility adapter for existing replay/diagnostic helpers."""

    if query.query_kind != "ReferenceAuditAll":
        raise SchemaError("only ReferenceAuditAll has a ReferenceProduct adapter")
    low_constraints = tuple(query.initial_constraints[2:])
    return ReferenceProduct(
        query.input_variables,
        (),
        low_constraints,
        query.bad_causes,
        query.goal,
    )
