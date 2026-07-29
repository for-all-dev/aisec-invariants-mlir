"""SMT-building helpers shared by the checkers.

All three drivers (`pdl_ct`, `structural`, `selfcomp`) build the same kind of object: a
few copies of a program, lowered to SMT inside one module, with their observation
traces compared. The pieces that do not depend on *which* comparison is being made live
here.
"""

from __future__ import annotations

from collections.abc import Sequence

from xdsl.builder import Builder
from xdsl.dialects.builtin import ArrayAttr
from xdsl.dialects.func import FuncOp
from xdsl.ir import Operation, SSAValue
from xdsl_smt.dialects import smt_bitvector_dialect as smt_bv
from xdsl_smt.dialects import smt_dialect as smt
from xdsl_smt.dialects import smt_utils_dialect as smt_utils
from xdsl_smt.dialects.effects.effect import StateType
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer

from .dialect import Observation, StructuralTrace, template_semantics
from .leakage import LeakageRule
from .predication import flatten


def as_bool(builder: Builder, value: SSAValue) -> SSAValue:
    """An `i1` guard, lowered to a bitvector pair, seen as an SMT boolean."""
    if isinstance(value.type, smt_utils.PairType):
        value = builder.insert(smt_utils.FirstOp(value)).res
    if isinstance(value.type, smt.BoolType):
        return value
    one = builder.insert(smt_bv.ConstantOp(1, 1)).res
    return builder.insert(smt.EqOp(value, one)).res


def observed_value(builder: Builder, value: SSAValue) -> SSAValue:
    """Drop the poison marker: what leaks is the value, not whether it is defined."""
    if isinstance(value.type, smt_utils.PairType) and isinstance(value.type.second, smt.BoolType):
        return builder.insert(smt_utils.FirstOp(value)).res
    return value


def conjoin(builder: Builder, terms: Sequence[SSAValue]) -> SSAValue:
    if not terms:
        return builder.insert(smt.ConstantBoolOp(True)).result
    result = terms[0]
    for term in terms[1:]:
        result = builder.insert(smt.AndOp(result, term)).result
    return result


def traces_agree(
    builder: Builder,
    left: Sequence[Observation],
    right: Sequence[Observation],
) -> SSAValue:
    """Same observations, in the same order, under the same guards.

    The guard is compared as well as the value: an observation inside a branch counts
    only when the branch is taken, and *which* branch is taken is itself observable.
    """
    terms: list[SSAValue] = []
    for one, other in zip(left, right, strict=True):
        guard_one = as_bool(builder, one.guard)
        guard_other = as_bool(builder, other.guard)
        terms.append(builder.insert(smt.EqOp(guard_one, guard_other)).res)
        same_value = builder.insert(
            smt.EqOp(
                observed_value(builder, one.value),
                observed_value(builder, other.value),
            )
        ).res
        terms.append(builder.insert(smt.ImpliesOp(guard_one, same_value)).result)
    return conjoin(builder, terms)


def instantiate(
    function: FuncOp,
    inputs: Sequence[SSAValue],
    builder: Builder,
    model: dict[type[Operation], LeakageRule] | None,
    max_visits: int,
    state: SSAValue | None = None,
) -> tuple[StructuralTrace, bool, SSAValue | None]:
    """Flatten one program, splice it in on the given inputs, and lower it to SMT.

    `state` is the effect state the program starts from. Two programs that must see the
    same initial memory are given the same one; two that must not interact (the source
    and the target of a lowering, where UB raised by one must not reach the other) each
    get a fresh one.
    """
    if state is None:
        state = builder.insert(smt.DeclareConstOp(StateType())).res
    program = flatten(function.clone(), model, max_visits)
    flat = program.block
    # Upstream's `LowerToSMTPass` stashes the pre-lowering operand types on every
    # operation, and semantics that need the source type read them back from there --
    # `memref.load` recovers the memref's shape this way. We lower operations one by
    # one rather than through that pass, so the same note has to be attached here, and
    # before the block arguments are replaced by SMT values.
    for op in flat.walk():
        op.attributes["__operand_types"] = ArrayAttr([operand.type for operand in op.operands])
    for argument, value in zip(list(flat.args), inputs, strict=True):
        argument.replace_by(value)

    trace = StructuralTrace()
    body = list(flat.ops)
    for op in body:
        op.detach()
        builder.insert(op)
    with template_semantics(trace):
        for op in body:
            state = SMTLowerer.lower_operation(op, state) or state
    return trace, program.bounded, state
