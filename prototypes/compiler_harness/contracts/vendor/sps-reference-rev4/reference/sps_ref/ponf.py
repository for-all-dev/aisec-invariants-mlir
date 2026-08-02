"""Canonical reference query construction.

The format is intentionally not the normative SPS-PONF-v2 format.
"""

from __future__ import annotations

from typing import Any

from .canonical import canonical_digest
from .engine import CompiledProgram
from .errors import SchemaError
from .model import Coalition
from .product import ReferenceProduct, build_product
from .smt import lower_reference_ponf, lower_reference_product
from .terms import collect_variables


def build_reference_ponf(
    left: CompiledProgram, right: CompiledProgram, coalition: Coalition
) -> dict[str, Any]:
    product = build_product(left, right, coalition)
    referenced = collect_variables(
        [*product.low_constraints, *(cause.expression for cause in product.bad_causes)]
    )
    variables = dict(product.input_variables)
    if len(variables) != len(product.input_variables):
        raise SchemaError("duplicate reference product input symbol")
    for name, width in referenced.items():
        if variables.get(name) != width:
            raise SchemaError(
                f"formula symbol {name} is absent or has the wrong width"
            )
    coalition_descriptor = {
        "coalitionId": coalition.coalition_id,
        "principals": sorted(coalition.principals),
        "controlledHosts": sorted(coalition.controlled_hosts),
    }
    canonical_program_digest = canonical_digest(left.program)
    coalition_descriptor_digest = canonical_digest(coalition_descriptor)
    exact_smt_digest = lower_reference_product(product).sha256
    artifact: dict[str, Any] = {
        "formatId": "SPS-Reference-PONF-v2",
        "claimBoundary": "ExecutableReferenceOnly",
        "entryId": left.program["entryId"],
        "coalitionId": coalition.coalition_id,
        "canonicalProgramDigest": canonical_program_digest,
        "coalitionDescriptor": coalition_descriptor,
        "coalitionDescriptorDigest": coalition_descriptor_digest,
        "leftExpandedCFGTableDigest": left.expansion["expandedCFGTableDigest"],
        "rightExpandedCFGTableDigest": right.expansion["expandedCFGTableDigest"],
        "exactSMTDigest": exact_smt_digest,
        "variables": [
            {"name": name, "sort": "BV", "width": variables[name]}
            for name in sorted(variables)
        ],
        "initialConstraints": [
            {"ordinal": index, "expression": expression.to_obj()}
            for index, expression in enumerate(product.low_constraints)
        ],
        "badCauseRows": [
            {
                "ordinal": index,
                "cause": cause.cause,
                "eventOrdinal": cause.event_ordinal,
                "expression": cause.expression.to_obj(),
            }
            for index, cause in enumerate(product.bad_causes)
        ],
        "goal": product.bad.to_obj(),
    }
    artifact["canonicalReferencePONFDigest"] = canonical_digest(artifact)
    return artifact


def build_product_and_ponf(
    left: CompiledProgram, right: CompiledProgram, coalition: Coalition
) -> tuple[ReferenceProduct, dict[str, Any]]:
    product = build_product(left, right, coalition)
    return product, build_reference_ponf(left, right, coalition)


def audit_reference_ponf(
    artifact: dict[str, Any],
    left: CompiledProgram,
    right: CompiledProgram,
    coalition: Coalition,
) -> None:
    """Independently reconstruct every decisive serialized PONF field."""

    serialized_smt = lower_reference_ponf(artifact)
    product = build_product(left, right, coalition)
    product_smt = lower_reference_product(product)
    if serialized_smt != product_smt:
        raise SchemaError("reference PONF lowering disagrees with product")

    descriptor = {
        "coalitionId": coalition.coalition_id,
        "principals": sorted(coalition.principals),
        "controlledHosts": sorted(coalition.controlled_hosts),
    }
    expected_static = {
        "formatId": "SPS-Reference-PONF-v2",
        "claimBoundary": "ExecutableReferenceOnly",
        "entryId": left.program["entryId"],
        "coalitionId": coalition.coalition_id,
        "canonicalProgramDigest": canonical_digest(left.program),
        "coalitionDescriptor": descriptor,
        "coalitionDescriptorDigest": canonical_digest(descriptor),
        "leftExpandedCFGTableDigest": left.expansion["expandedCFGTableDigest"],
        "rightExpandedCFGTableDigest": right.expansion["expandedCFGTableDigest"],
        "exactSMTDigest": product_smt.sha256,
    }
    for field, expected in expected_static.items():
        if artifact.get(field) != expected:
            raise SchemaError(f"reference PONF field {field} disagrees")

    variables = dict(product.input_variables)
    expected_variables = [
        {"name": name, "sort": "BV", "width": variables[name]}
        for name in sorted(variables)
    ]
    expected_constraints = [
        {"ordinal": index, "expression": expression.to_obj()}
        for index, expression in enumerate(product.low_constraints)
    ]
    expected_bad_rows = [
        {
            "ordinal": index,
            "cause": cause.cause,
            "eventOrdinal": cause.event_ordinal,
            "expression": cause.expression.to_obj(),
        }
        for index, cause in enumerate(product.bad_causes)
    ]
    if artifact.get("variables") != expected_variables:
        raise SchemaError("reference PONF variable plan disagrees")
    if artifact.get("initialConstraints") != expected_constraints:
        raise SchemaError("reference PONF initial constraints disagree")
    if artifact.get("badCauseRows") != expected_bad_rows:
        raise SchemaError("reference PONF bad-source rows disagree")
    if artifact.get("goal") != product.bad.to_obj():
        raise SchemaError("reference PONF goal disagrees")
