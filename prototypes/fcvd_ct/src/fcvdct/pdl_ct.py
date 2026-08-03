r"""Constant-time preservation for a PDL rewrite, proved for every program it matches.

The property
------------

A rewrite rule turns a source program S into a target program T. Both are symbolic:
their inputs are the operands the pattern binds. Writing L_S(x) for the sequence of
observations the leakage model attributes to S on inputs x, the rule preserves
constant-time when

    forall x, x'.  L_S(x) = L_S(x')  ==>  L_T(x) = L_T(x')

i.e. any two inputs the *original* code was already unable to tell apart stay
indistinguishable after the rewrite. The rule may remove leakage, never add it.

Two things are worth noting about this formulation. It needs no secret/public
labelling: the source program's own leakage is the declassification bound, which is
what makes the statement hold for *every* program the pattern matches rather than for
one labelled kernel. And it is a 2-hypersafety property, so it is checked by
self-composition: two independent instantiations of the same pattern, related by the
formula above.

The encoding
------------

Each instantiation is lowered by upstream's `pdl-to-smt`, with the value-refinement
criterion replaced by a constant `false`. That is not a trick to disable checking: it
makes the assertion upstream emits collapse to exactly `preconditions /\ not ub`, the
assumption under which the rule is allowed to fire, which is what we want to assume
before adding our own obligation. The obligation itself is appended afterwards:

    assert(L_S(x) = L_S(x')  /\  L_T(x) != L_T(x'))

`unsat` = the rewrite preserves constant-time for all matching programs; `sat` = z3
hands back two concrete inputs that the source cannot distinguish and the target can.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO
from typing import Literal

from xdsl.builder import Builder
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation, SSAValue
from xdsl.rewriter import InsertPoint
from xdsl.transforms.canonicalize import CanonicalizePass
from xdsl.transforms.common_subexpression_elimination import (
    CommonSubexpressionElimination,
)
from xdsl_smt.dialects import smt_dialect as smt
from xdsl_smt.dialects import smt_utils_dialect as smt_utils
from xdsl_smt.passes.dead_code_elimination import DeadCodeElimination
from xdsl_smt.passes.lower_effects import LowerEffectPass
from xdsl_smt.passes.lower_pairs import LowerPairs
from xdsl_smt.passes.pdl_to_smt import PDLToSMT
from xdsl_smt.passes.smt_expand import SMTExpand
from xdsl_smt.pdl_constraints.integer_arith_constraints import (
    integer_arith_native_constraints,
    integer_arith_native_rewrites,
    integer_arith_native_static_constraints,
)
from xdsl_smt.semantics.semantics import RefinementSemantics
from xdsl_smt.traits.smt_printer import print_to_smtlib

from .leakage import LeakageRule, LeakageTrace, recording

Verdict = Literal["ct-preserving", "ct-breaking", "unknown"]


class _AssumeMatchOnly(RefinementSemantics):
    """A refinement that is always false.

    Upstream builds `ub_before \\/ (not ub_after /\\ refinement)` and asserts its
    negation together with the pattern's preconditions. With `refinement = false` that
    assertion becomes `not ub_before /\\ preconditions`: the rewrite's own applicability
    conditions, and nothing about values. We want those as assumptions, and we supply
    the obligation ourselves.
    """

    def get_semantics(
        self, val_before: SSAValue, val_after: SSAValue, builder: Builder
    ) -> SSAValue:
        return builder.insert(smt.ConstantBoolOp(False)).result


@dataclass
class CTResult:
    verdict: Verdict
    n_source_observations: int
    n_target_observations: int
    smtlib: str
    solver_output: str = ""
    counterexample: str = ""
    reason: str = ""


def _configure_lowerer() -> None:
    PDLToSMT.pdl_lowerer.native_rewrites = integer_arith_native_rewrites
    PDLToSMT.pdl_lowerer.native_constraints = integer_arith_native_constraints
    # Upstream declares the field with positional-only parameters and populates it with
    # named-parameter functions; the mismatch is theirs, and `verify-pdl` does the same.
    PDLToSMT.pdl_lowerer.native_static_constraints = integer_arith_native_static_constraints  # ty: ignore[invalid-assignment]
    PDLToSMT.pdl_lowerer.refinement = _AssumeMatchOnly()


def _lower_instance(
    ctx: Context,
    pattern: ModuleOp,
    model: dict[type[Operation], LeakageRule] | None,
) -> tuple[ModuleOp, LeakageTrace]:
    """Lower one instantiation of the pattern, recording what it leaks."""
    instance = pattern.clone()
    with recording(model) as trace:
        PDLToSMT().apply(ctx, instance)
    # Upstream ends the query with its own `check-sat`; ours comes after both
    # instantiations have been composed.
    for op in list(instance.body.block.ops):
        if isinstance(op, smt.CheckSatOp):
            instance.body.block.erase_op(op)
    return instance, trace


def _value_of(builder: Builder, observation: SSAValue) -> SSAValue:
    """An observation is what the hardware sees: the value, not the poison flag."""
    if isinstance(observation.type, smt_utils.PairType):
        return builder.insert(smt_utils.FirstOp(observation)).res
    return observation


def _all_equal(builder: Builder, left: Sequence[SSAValue], right: Sequence[SSAValue]) -> SSAValue:
    conjuncts: list[SSAValue] = []
    for lhs, rhs in zip(left, right, strict=True):
        conjuncts.append(
            builder.insert(smt.EqOp(_value_of(builder, lhs), _value_of(builder, rhs))).res
        )
    if not conjuncts:
        return builder.insert(smt.ConstantBoolOp(True)).result
    result = conjuncts[0]
    for conjunct in conjuncts[1:]:
        result = builder.insert(smt.AndOp(result, conjunct)).result
    return result


def build_query(
    ctx: Context,
    pattern: ModuleOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
) -> tuple[str, int, int]:
    """Build the SMTLib script asserting that the rewrite *breaks* constant-time."""
    _configure_lowerer()

    first, first_trace = _lower_instance(ctx, pattern, model)
    second, second_trace = _lower_instance(ctx, pattern, model)

    if len(first_trace.source) != len(second_trace.source) or len(first_trace.target) != len(
        second_trace.target
    ):
        raise AssertionError(
            "the two instantiations of the same pattern disagree on the number of "
            "observations, which should be impossible"
        )

    # Compose: one module holding both instantiations. Detaching keeps the SSA values
    # the leakage traces point at intact.
    block = first.body.block
    for op in list(second.body.block.ops):
        op.detach()
        block.add_op(op)

    builder = Builder(InsertPoint.at_end(block))
    same_source = _all_equal(builder, first_trace.source, second_trace.source)
    same_target = _all_equal(builder, first_trace.target, second_trace.target)
    differs = builder.insert(smt.NotOp(same_target)).result
    obligation = builder.insert(smt.AndOp(same_source, differs)).result
    builder.insert(smt.AssertOp(obligation))
    builder.insert(smt.CheckSatOp())

    LowerEffectPass().apply(ctx, first)
    SMTExpand().apply(ctx, first)
    if opt:
        LowerPairs().apply(ctx, first)
        CanonicalizePass().apply(ctx, first)
        CommonSubexpressionElimination().apply(ctx, first)
        CanonicalizePass().apply(ctx, first)
        DeadCodeElimination().apply(ctx, first)
    first.verify()

    stream = StringIO()
    print_to_smtlib(first, stream)
    return stream.getvalue(), len(first_trace.source), len(first_trace.target)


def _run_z3(script: str, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["z3", "-in", f"-T:{timeout}"],
        capture_output=True,
        input=script,
        text=True,
    )


def check_pattern(
    ctx: Context,
    pattern: ModuleOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    timeout: int = 60,
) -> CTResult:
    """Decide whether one `pdl.pattern` preserves constant-time for every match."""
    try:
        script, n_source, n_target = build_query(ctx, pattern, model, opt)
    except Exception as e:  # unsupported op, unsupported type, upstream limitation
        return CTResult("unknown", 0, 0, "", reason=f"{type(e).__name__}: {e}")

    result = _run_z3(script, timeout)
    output = result.stdout.strip()

    if output.startswith("unsat"):
        return CTResult("ct-preserving", n_source, n_target, script, output)
    if output.startswith("sat"):
        model_out = _run_z3(script + "\n(get-model)\n", timeout)
        return CTResult("ct-breaking", n_source, n_target, script, output, model_out.stdout.strip())
    return CTResult(
        "unknown",
        n_source,
        n_target,
        script,
        output,
        reason=f"solver said {output or '<nothing>'}; stderr: {result.stderr.strip()}",
    )
