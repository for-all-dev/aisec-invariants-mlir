"""Two-lane product and bad-state construction for the reference slice."""

from __future__ import annotations

from dataclasses import dataclass

from .engine import (
    CompiledProgram,
    ReferenceEvent,
    assert_compiled_integrity,
    event_value_visible,
)
from .errors import SchemaError
from .model import Coalition
from .terms import Term, bool_and, bool_lit, bool_not, bool_or, bool_xor, equal


@dataclass(frozen=True)
class BadCause:
    cause: str
    event_ordinal: int
    expression: Term


@dataclass(frozen=True)
class ReferenceProduct:
    input_variables: tuple[tuple[str, int], ...]
    low_input_pairs: tuple[tuple[str, str, int], ...]
    low_constraints: tuple[Term, ...]
    bad_causes: tuple[BadCause, ...]
    bad: Term


def build_product(
    left: CompiledProgram, right: CompiledProgram, coalition: Coalition
) -> ReferenceProduct:
    assert_compiled_integrity(left)
    assert_compiled_integrity(right)
    if left.lane != "L" or right.lane != "R":
        raise SchemaError("reference product requires canonical L and R lanes")
    if left.program_bytes != right.program_bytes:
        raise SchemaError("reference product lanes must use one program")
    if len(left.events) != len(right.events):
        raise SchemaError("reference product event inventories disagree")

    low_constraints = tuple(
        equal(
            left.input_symbols[decl.input_id],
            right.input_symbols[decl.input_id],
        )
        for decl in left.inputs
        if decl.classification == "Low"
    )
    active = bool_lit(True)
    causes: list[BadCause] = []

    for ordinal, (left_event, right_event) in enumerate(
        zip(left.events, right.events, strict=True)
    ):
        static_mismatch = _static_mismatch(left_event, right_event)
        present_mismatch = bool_and(
            active, bool_xor(left_event.present, right_event.present)
        )
        causes.append(BadCause("EventAlignment", ordinal, present_mismatch))

        both = bool_and(active, left_event.present, right_event.present)
        site_order = bool_and(
            both,
            bool_or(
                bool_lit(static_mismatch),
                bool_not(equal(left_event.visit, right_event.visit)),
            ),
        )
        causes.append(BadCause("SiteOrderAlignment", ordinal, site_order))

        structural_values = _structural_terms(left_event, right_event)
        structural_mismatch = _term_sequence_mismatch(structural_values)
        if structural_mismatch is not None:
            causes.append(
                BadCause(
                    "ProjectedPayloadMismatch",
                    ordinal,
                    bool_and(both, structural_mismatch),
                )
            )

        payload_mismatch = _term_sequence_mismatch(
            list(zip(left_event.value_bytes, right_event.value_bytes, strict=False))
        )
        authorized_release = (
            left_event.kind == "Release"
            and bool(left_event.audience & coalition.principals)
        )
        payload_visible = event_value_visible(left_event, coalition)
        if payload_mismatch is not None and payload_visible:
            payload_bad = bool_and(both, payload_mismatch)
            if authorized_release:
                # The exact reference fixtures use complete value footprints.
                if left_event.footprint_bytes != tuple(
                    range(len(left_event.value_bytes))
                ):
                    raise UnsupportedErrorForProduct(
                        "reference release retirement requires a full-byte footprint"
                    )
                active = bool_and(active, bool_not(payload_bad))
            else:
                causes.append(
                    BadCause("ProjectedPayloadMismatch", ordinal, payload_bad)
                )

    bad_terms = tuple(cause.expression for cause in causes)
    input_variables = tuple(
        sorted(
            (
                (symbol.name, int(symbol.width))
                for compiled in (left, right)
                for symbol in compiled.symbolic_inputs
                if symbol.name is not None and symbol.width is not None
            ),
            key=lambda row: row[0],
        )
    )
    return ReferenceProduct(
        input_variables=input_variables,
        low_input_pairs=tuple(
            (
                f"L.input.{decl.input_id}",
                f"R.input.{decl.input_id}",
                decl.width,
            )
            for decl in left.inputs
            if decl.classification == "Low"
        ),
        low_constraints=low_constraints,
        bad_causes=tuple(causes),
        bad=bool_or(*bad_terms),
    )


class UnsupportedErrorForProduct(SchemaError):
    reason = "ReferenceProductUnsupported"


def _static_mismatch(left: ReferenceEvent, right: ReferenceEvent) -> bool:
    return any(
        [
            left.kind != right.kind,
            left.site != right.site,
            left.within_ordinal != right.within_ordinal,
            left.output_id != right.output_id,
            left.release_id != right.release_id,
            left.audience != right.audience,
            left.footprint_bytes != right.footprint_bytes,
            left.transfer_source != right.transfer_source,
            left.transfer_destinations != right.transfer_destinations,
            left.bound_id != right.bound_id,
            left.snapshot_names != right.snapshot_names,
        ]
    )


def _structural_terms(
    left: ReferenceEvent, right: ReferenceEvent
) -> list[tuple[Term, Term]]:
    pairs: list[tuple[Term, Term]] = []
    if left.kind in {"BranchSuccessor", "LoopContinuation"}:
        pairs.extend(zip(left.value_bytes, right.value_bytes, strict=True))
    if left.kind == "Release":
        if left.release_ordinal is None or right.release_ordinal is None:
            raise SchemaError("release event lacks its dynamic ordinal")
        pairs.append((left.release_ordinal, right.release_ordinal))
    return pairs


def _term_sequence_mismatch(
    pairs: list[tuple[Term, Term]],
) -> Term | None:
    if not pairs:
        return None
    return bool_or(*(bool_not(equal(left, right)) for left, right in pairs))
