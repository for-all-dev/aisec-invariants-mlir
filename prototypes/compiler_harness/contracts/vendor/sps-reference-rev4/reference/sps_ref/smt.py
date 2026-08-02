"""Deterministic SMT-LIB lowering for reference queries and PONF v3."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .canonical import canonical_digest
from .errors import SchemaError
from .product import ReferenceProduct
from .terms import Term, bool_or, collect_variables, quote_symbol, term_from_obj


@dataclass(frozen=True)
class SMTArtifact:
    text: str
    sha256: str
    variables: tuple[tuple[str, int], ...]


def lower_reference_product(product: ReferenceProduct) -> SMTArtifact:
    variables = dict(product.input_variables)
    if len(variables) != len(product.input_variables):
        raise ValueError("duplicate reference product input symbol")
    referenced = collect_variables([*product.low_constraints, product.bad])
    for name, width in referenced.items():
        if variables.get(name) != width:
            raise ValueError(f"formula symbol {name} is absent or has the wrong width")
    return _lower_terms(
        tuple(sorted(variables.items())),
        product.low_constraints,
        product.bad,
    )


def lower_reference_query(query: Any) -> SMTArtifact:
    variables = tuple(sorted(query.input_variables))
    if len(dict(variables)) != len(variables):
        raise SchemaError("duplicate reference query input symbol")
    return _lower_terms(variables, query.initial_constraints, query.goal)


def lower_reference_ponf(artifact: dict[str, Any]) -> SMTArtifact:
    """Lower the serialized reference PONF rather than a parallel product."""

    expected_fields = {
        "formatId",
        "claimBoundary",
        "query",
        "entryId",
        "coalitionId",
        "canonicalProgramDigest",
        "coalitionDescriptor",
        "coalitionDescriptorDigest",
        "leftExpandedCFGTableDigest",
        "rightExpandedCFGTableDigest",
        "exactSMTDigest",
        "variables",
        "initialConstraints",
        "auditBadCauseRows",
        "goal",
        "canonicalReferencePONFDigest",
    }
    if not isinstance(artifact, dict) or set(artifact) != expected_fields:
        raise SchemaError("reference PONF field mismatch")
    if (
        artifact["formatId"] != "SPS-Reference-PONF-v3"
        or artifact["claimBoundary"] != "ExecutableReferenceOnly"
    ):
        raise SchemaError("wrong reference PONF format")
    query = artifact["query"]
    if (
        not isinstance(query, dict)
        or set(query) != {"kind", "componentId"}
        or query["kind"]
        not in {
            "ReferenceAdmissionNonempty",
            "ReferenceHighVariation",
            "ReferenceTerminalOutputSurface",
            "ReferenceAuditAll",
        }
        or (
            query["kind"] == "ReferenceHighVariation"
            and not isinstance(query["componentId"], str)
        )
        or (
            query["kind"] != "ReferenceHighVariation"
            and query["componentId"] is not None
        )
    ):
        raise SchemaError("malformed reference PONF query descriptor")
    for field in (
        "canonicalProgramDigest",
        "coalitionDescriptorDigest",
        "leftExpandedCFGTableDigest",
        "rightExpandedCFGTableDigest",
        "exactSMTDigest",
        "canonicalReferencePONFDigest",
    ):
        if not _is_digest(artifact[field]):
            raise SchemaError(f"reference PONF {field} is not a digest")
    digest_preimage = dict(artifact)
    recorded_ponf_digest = digest_preimage.pop("canonicalReferencePONFDigest")
    if canonical_digest(digest_preimage) != recorded_ponf_digest:
        raise SchemaError("reference PONF canonical digest mismatch")
    descriptor = artifact["coalitionDescriptor"]
    if (
        not isinstance(descriptor, dict)
        or set(descriptor) != {"coalitionId", "principals", "controlledHosts"}
        or descriptor["coalitionId"] != artifact["coalitionId"]
    ):
        raise SchemaError("reference PONF coalition descriptor mismatch")
    for field in ("principals", "controlledHosts"):
        members = descriptor[field]
        if (
            not isinstance(members, list)
            or not all(isinstance(member, str) and member for member in members)
            or members != sorted(set(members))
        ):
            raise SchemaError(f"reference PONF coalition {field} is noncanonical")
    if canonical_digest(descriptor) != artifact["coalitionDescriptorDigest"]:
        raise SchemaError("reference PONF coalition descriptor digest mismatch")
    raw_variables = artifact.get("variables")
    if not isinstance(raw_variables, list):
        raise SchemaError("reference PONF variables must be a list")
    variables: list[tuple[str, int]] = []
    for index, row in enumerate(raw_variables):
        if (
            not isinstance(row, dict)
            or set(row) != {"name", "sort", "width"}
            or row.get("sort") != "BV"
            or not isinstance(row.get("name"), str)
            or not row["name"]
            or not isinstance(row.get("width"), int)
            or isinstance(row["width"], bool)
            or row["width"] <= 0
        ):
            raise SchemaError(f"malformed reference PONF variable {index}")
        variables.append((row["name"], row["width"]))
    ordered_variables = tuple(variables)
    if (
        ordered_variables != tuple(sorted(ordered_variables))
        or len(dict(ordered_variables)) != len(ordered_variables)
    ):
        raise SchemaError("reference PONF variables are not sorted and unique")

    raw_constraints = artifact.get("initialConstraints")
    if not isinstance(raw_constraints, list):
        raise SchemaError("reference PONF initialConstraints must be a list")
    constraints: list[Term] = []
    for index, row in enumerate(raw_constraints):
        if (
            not isinstance(row, dict)
            or set(row) != {"ordinal", "expression"}
            or not isinstance(row["ordinal"], int)
            or isinstance(row["ordinal"], bool)
            or row["ordinal"] != index
        ):
            raise SchemaError(f"malformed reference PONF constraint {index}")
        constraint = term_from_obj(row["expression"])
        if constraint.sort != "Bool":
            raise SchemaError(f"reference PONF constraint {index} is not Boolean")
        constraints.append(constraint)
    goal = term_from_obj(artifact.get("goal"))
    if goal.sort != "Bool":
        raise SchemaError("reference PONF goal is not Boolean")
    raw_bad_rows = artifact["auditBadCauseRows"]
    if not isinstance(raw_bad_rows, list):
        raise SchemaError("reference PONF auditBadCauseRows must be a list")
    bad_terms: list[Term] = []
    for index, row in enumerate(raw_bad_rows):
        if (
            not isinstance(row, dict)
            or set(row) != {"ordinal", "cause", "eventOrdinal", "expression"}
            or not isinstance(row["ordinal"], int)
            or isinstance(row["ordinal"], bool)
            or row["ordinal"] != index
            or row["cause"]
            not in {
                "EventAlignment",
                "SiteOrderAlignment",
                "ProjectedPayloadMismatch",
            }
            or not isinstance(row["eventOrdinal"], int)
            or isinstance(row["eventOrdinal"], bool)
            or row["eventOrdinal"] < 0
        ):
            raise SchemaError(f"malformed reference PONF bad row {index}")
        bad_term = term_from_obj(row["expression"])
        if bad_term.sort != "Bool":
            raise SchemaError(f"reference PONF bad row {index} is not Boolean")
        bad_terms.append(bad_term)
    if query["kind"] == "ReferenceAuditAll":
        if bool_or(*bad_terms) != goal:
            raise SchemaError("reference PONF bad rows do not reconstruct the goal")
    elif bad_terms:
        raise SchemaError("non-AuditAll reference PONF contains audit bad rows")
    result = _lower_terms(ordered_variables, tuple(constraints), goal)
    if artifact.get("exactSMTDigest") != result.sha256:
        raise SchemaError("reference PONF exact SMT digest mismatch")
    return result


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _lower_terms(
    ordered_variables: tuple[tuple[str, int], ...],
    constraints: tuple[Term, ...],
    goal: Term,
) -> SMTArtifact:
    declared = dict(ordered_variables)
    if len(declared) != len(ordered_variables):
        raise SchemaError("duplicate SMT variable")
    referenced = collect_variables([*constraints, goal])
    for name, width in referenced.items():
        if declared.get(name) != width:
            raise SchemaError(f"undeclared or wrong-width formula symbol {name}")
    lines = ["(set-option :produce-models true)", "(set-logic QF_BV)"]
    for name, width in ordered_variables:
        lines.append(
            f"(declare-fun {quote_symbol(name)} () (_ BitVec {width}))"
        )
    for constraint in constraints:
        lines.append(f"(assert {constraint.to_smt()})")
    lines.append(f"(assert {goal.to_smt()})")
    lines.append("(check-sat)")
    text = "\n".join(lines) + "\n"
    return SMTArtifact(
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        variables=ordered_variables,
    )
