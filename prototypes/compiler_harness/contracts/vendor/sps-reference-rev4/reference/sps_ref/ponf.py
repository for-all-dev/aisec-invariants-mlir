"""Canonical, non-normative reference query construction and auditing."""

from __future__ import annotations

from typing import Any

from .canonical import canonical_digest
from .engine import CompiledProgram
from .errors import SchemaError
from .model import Coalition
from .query import ReferenceQuery, build_reference_query
from .smt import lower_reference_ponf, lower_reference_query
from .terms import collect_variables


def build_reference_ponf(
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    query_kind: str = "ReferenceAuditAll",
    component_id: str | None = None,
) -> dict[str, Any]:
    query = build_reference_query(
        left, right, coalition, query_kind, component_id
    )
    referenced = collect_variables([*query.initial_constraints, query.goal])
    variables = dict(query.input_variables)
    if len(variables) != len(query.input_variables):
        raise SchemaError("duplicate reference query input symbol")
    for name, width in referenced.items():
        if variables.get(name) != width:
            raise SchemaError(
                f"formula symbol {name} is absent or has the wrong width"
            )
    descriptor = _coalition_descriptor(coalition)
    artifact: dict[str, Any] = {
        "formatId": "SPS-Reference-PONF-v3",
        "claimBoundary": "ExecutableReferenceOnly",
        "query": {"kind": query.query_kind, "componentId": query.component_id},
        "entryId": left.program["entryId"],
        "coalitionId": coalition.coalition_id,
        "canonicalProgramDigest": canonical_digest(left.program),
        "coalitionDescriptor": descriptor,
        "coalitionDescriptorDigest": canonical_digest(descriptor),
        "leftExpandedCFGTableDigest": left.expansion["expandedCFGTableDigest"],
        "rightExpandedCFGTableDigest": right.expansion["expandedCFGTableDigest"],
        "exactSMTDigest": lower_reference_query(query).sha256,
        "variables": [
            {"name": name, "sort": "BV", "width": variables[name]}
            for name in sorted(variables)
        ],
        "initialConstraints": [
            {"ordinal": index, "expression": expression.to_obj()}
            for index, expression in enumerate(query.initial_constraints)
        ],
        "auditBadCauseRows": [
            {
                "ordinal": index,
                "cause": cause.cause,
                "eventOrdinal": cause.event_ordinal,
                "expression": cause.expression.to_obj(),
            }
            for index, cause in enumerate(query.bad_causes)
        ],
        "goal": query.goal.to_obj(),
    }
    artifact["canonicalReferencePONFDigest"] = canonical_digest(artifact)
    return artifact


def build_query_and_ponf(
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    query_kind: str,
    component_id: str | None = None,
) -> tuple[ReferenceQuery, dict[str, Any]]:
    query = build_reference_query(
        left, right, coalition, query_kind, component_id
    )
    return query, build_reference_ponf(
        left, right, coalition, query_kind, component_id
    )


def audit_reference_ponf(
    artifact: dict[str, Any],
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
    query_kind: str = "ReferenceAuditAll",
    component_id: str | None = None,
) -> None:
    """Independently reconstruct every decisive serialized PONF field."""

    query = build_reference_query(
        left, right, coalition, query_kind, component_id
    )
    serialized_smt = lower_reference_ponf(artifact)
    direct_smt = lower_reference_query(query)
    if serialized_smt != direct_smt:
        raise SchemaError("reference PONF lowering disagrees with direct query")
    descriptor = _coalition_descriptor(coalition)
    expected_static = {
        "formatId": "SPS-Reference-PONF-v3",
        "claimBoundary": "ExecutableReferenceOnly",
        "query": {"kind": query.query_kind, "componentId": query.component_id},
        "entryId": left.program["entryId"],
        "coalitionId": coalition.coalition_id,
        "canonicalProgramDigest": canonical_digest(left.program),
        "coalitionDescriptor": descriptor,
        "coalitionDescriptorDigest": canonical_digest(descriptor),
        "leftExpandedCFGTableDigest": left.expansion["expandedCFGTableDigest"],
        "rightExpandedCFGTableDigest": right.expansion["expandedCFGTableDigest"],
        "exactSMTDigest": direct_smt.sha256,
    }
    for field, expected in expected_static.items():
        if artifact.get(field) != expected:
            raise SchemaError(f"reference PONF field {field} disagrees")
    variables = dict(query.input_variables)
    expected_variables = [
        {"name": name, "sort": "BV", "width": variables[name]}
        for name in sorted(variables)
    ]
    expected_constraints = [
        {"ordinal": index, "expression": expression.to_obj()}
        for index, expression in enumerate(query.initial_constraints)
    ]
    expected_rows = [
        {
            "ordinal": index,
            "cause": cause.cause,
            "eventOrdinal": cause.event_ordinal,
            "expression": cause.expression.to_obj(),
        }
        for index, cause in enumerate(query.bad_causes)
    ]
    if artifact.get("variables") != expected_variables:
        raise SchemaError("reference PONF variable plan disagrees")
    if artifact.get("initialConstraints") != expected_constraints:
        raise SchemaError("reference PONF initial constraints disagree")
    if artifact.get("auditBadCauseRows") != expected_rows:
        raise SchemaError("reference PONF audit bad-source rows disagree")
    if artifact.get("goal") != query.goal.to_obj():
        raise SchemaError("reference PONF goal disagrees")


def _coalition_descriptor(coalition: Coalition) -> dict[str, Any]:
    return {
        "coalitionId": coalition.coalition_id,
        "principals": sorted(coalition.principals),
        "controlledHosts": sorted(coalition.controlled_hosts),
    }
