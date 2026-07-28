r"""Constant-time preservation of a *structural lowering specification*.

A lowering step like `scf.if` -> `cf.cond_br` is not a value rewrite on a fixed
program: it is a template over arbitrary surrounding code. Written as one, it is still
a two-program object, so the property is the same one `pdl_ct.py` proves for PDL
rewrites --

    forall x, x'.  L_source(x) = L_source(x')  ==>  L_target(x) = L_target(x')

-- but the quantification is stronger. The code inside the branches is a hole, and a
hole is an uninterpreted function, so a proof here holds for *every* program the
template can be instantiated with, not only for the operations we gave semantics to.

The encoding builds four programs: source and target, each run twice. Runs share
nothing; source and target within a run share their inputs. Then:

- every hole instance with the same name is tied to every other by a congruence axiom
  (equal inputs => equal outputs), which is what makes it a function rather than a
  fresh unknown each time;
- observations are guarded, and traces are compared as
  `same guards /\ (guard -> same value)`, so an observation inside a branch counts
  only when that branch is taken;
- `assert(source traces agree /\ target traces differ)` and `check-sat`.

`unsat` = the lowering adds no observation the source did not already make. `sat` = it
does, and z3 says on which inputs.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from io import StringIO
from typing import Literal

from xdsl.builder import Builder
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.dialects.func import FuncOp
from xdsl.ir import Operation, SSAValue
from xdsl.rewriter import InsertPoint
from xdsl.transforms.canonicalize import CanonicalizePass
from xdsl.transforms.common_subexpression_elimination import (
    CommonSubexpressionElimination,
)
from xdsl_smt.dialects import smt_bitvector_dialect as smt_bv
from xdsl_smt.dialects import smt_dialect as smt
from xdsl_smt.dialects import smt_utils_dialect as smt_utils
from xdsl_smt.dialects.effects.effect import StateType
from xdsl_smt.passes.dead_code_elimination import DeadCodeElimination
from xdsl_smt.passes.lower_effects import LowerEffectPass
from xdsl_smt.passes.lower_pairs import LowerPairs
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.passes.smt_expand import SMTExpand
from xdsl_smt.traits.smt_printer import print_to_smtlib

from .dialect import HoleOp, HoleSemantics, ObserveOp, ObserveSemantics, StructuralTrace
from .leakage import LeakageRule
from .predication import DEFAULT_MAX_VISITS, UnsupportedTemplate, flatten

Verdict = Literal["ct-preserving", "ct-breaking", "unknown"]


@dataclass
class LoweringResult:
    verdict: Verdict
    n_source_observations: int
    n_target_observations: int
    smtlib: str
    solver_output: str = ""
    counterexample: str = ""
    reason: str = ""
    bounded: bool = False
    """A path was cut by the unrolling bound, so the verdict only covers that many
    iterations. Reported, never hidden."""


@contextmanager
def _template_semantics(trace: StructuralTrace) -> Iterator[None]:
    """Give the template operations semantics for the duration of one lowering."""
    saved = SMTLowerer.op_semantics
    SMTLowerer.op_semantics = {
        **saved,
        HoleOp: HoleSemantics(trace),
        ObserveOp: ObserveSemantics(trace),
    }
    try:
        yield
    finally:
        SMTLowerer.op_semantics = saved


def _as_bool(builder: Builder, value: SSAValue) -> SSAValue:
    """An `i1` guard, lowered to a bitvector pair, seen as an SMT boolean."""
    if isinstance(value.type, smt_utils.PairType):
        value = builder.insert(smt_utils.FirstOp(value)).res
    if isinstance(value.type, smt.BoolType):
        return value
    one = builder.insert(smt_bv.ConstantOp(1, 1)).res
    return builder.insert(smt.EqOp(value, one)).res


def _observed_value(builder: Builder, value: SSAValue) -> SSAValue:
    if isinstance(value.type, smt_utils.PairType):
        return builder.insert(smt_utils.FirstOp(value)).res
    return value


def _conjoin(builder: Builder, terms: Sequence[SSAValue]) -> SSAValue:
    if not terms:
        return builder.insert(smt.ConstantBoolOp(True)).result
    result = terms[0]
    for term in terms[1:]:
        result = builder.insert(smt.AndOp(result, term)).result
    return result


def _traces_agree(builder: Builder, left: StructuralTrace, right: StructuralTrace) -> SSAValue:
    """Same observations, in the same order, under the same guards."""
    terms: list[SSAValue] = []
    for one, other in zip(left.observations, right.observations, strict=True):
        guard_one = _as_bool(builder, one.guard)
        guard_other = _as_bool(builder, other.guard)
        terms.append(builder.insert(smt.EqOp(guard_one, guard_other)).res)
        same_value = builder.insert(
            smt.EqOp(
                _observed_value(builder, one.value),
                _observed_value(builder, other.value),
            )
        ).res
        terms.append(builder.insert(smt.ImpliesOp(guard_one, same_value)).result)
    return _conjoin(builder, terms)


def _hole_congruence(builder: Builder, traces: Sequence[StructuralTrace]) -> list[SSAValue]:
    """Equal inputs give equal outputs, for every pair of occurrences of a hole."""
    by_name: dict[str, list[tuple[tuple[SSAValue, ...], tuple[SSAValue, ...]]]] = {}
    for trace in traces:
        for hole in trace.holes:
            by_name.setdefault(hole.sym_name, []).append((hole.inputs, hole.outputs))

    axioms: list[SSAValue] = []
    for occurrences in by_name.values():
        for index, (inputs, outputs) in enumerate(occurrences):
            for other_inputs, other_outputs in occurrences[index + 1 :]:
                if len(inputs) != len(other_inputs) or len(outputs) != len(other_outputs):
                    raise UnsupportedTemplate("the same hole is used with different signatures")
                same_inputs = _conjoin(
                    builder,
                    [
                        builder.insert(smt.EqOp(one, other)).res
                        for one, other in zip(inputs, other_inputs, strict=True)
                    ],
                )
                same_outputs = _conjoin(
                    builder,
                    [
                        builder.insert(smt.EqOp(one, other)).res
                        for one, other in zip(outputs, other_outputs, strict=True)
                    ],
                )
                axioms.append(builder.insert(smt.ImpliesOp(same_inputs, same_outputs)).result)
    return axioms


def _instantiate(
    function: FuncOp,
    inputs: Sequence[SSAValue],
    block_builder: Builder,
    model: dict[type[Operation], LeakageRule] | None,
    max_visits: int,
) -> tuple[StructuralTrace, bool]:
    """Flatten one program, splice it in on the given inputs, and lower it to SMT."""
    # Each program starts from its own effect state: UB raised by one of the four must
    # not propagate into the others.
    state: SSAValue | None = block_builder.insert(smt.DeclareConstOp(StateType())).res
    program = flatten(function.clone(), model, max_visits)
    flat = program.block
    for argument, value in zip(list(flat.args), inputs, strict=True):
        argument.replace_by(value)

    trace = StructuralTrace()
    body = [op for op in flat.ops]
    for op in body:
        op.detach()
        block_builder.insert(op)
    with _template_semantics(trace):
        for op in body:
            state = SMTLowerer.lower_operation(op, state) or state
    return trace, program.bounded


def build_query(
    ctx: Context,
    template: ModuleOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> tuple[str, int, int, bool]:
    """Build the SMTLib script asserting that the lowering *breaks* constant-time."""
    functions = {op.sym_name.data: op for op in template.body.ops if isinstance(op, FuncOp)}
    if set(functions) != {"source", "target"}:
        raise UnsupportedTemplate(
            "a template must contain exactly two functions, @source and @target, "
            f"found {sorted(functions)}"
        )
    source, target = functions["source"], functions["target"]
    if source.function_type.inputs != target.function_type.inputs:
        raise UnsupportedTemplate("@source and @target must take the same inputs")

    module = ModuleOp([])
    builder = Builder(InsertPoint.at_end(module.body.block))

    bounded = False
    traces: list[StructuralTrace] = []
    source_traces: list[StructuralTrace] = []
    target_traces: list[StructuralTrace] = []
    for run in range(2):
        inputs: list[SSAValue] = []
        for index, input_type in enumerate(source.function_type.inputs):
            declared = builder.insert(smt.DeclareConstOp(SMTLowerer.lower_type(input_type)))
            declared.res.name_hint = f"in{index}_run{run}"
            inputs.append(declared.res)
        # Source and target of one run see the same inputs; the two runs do not.
        source_trace, source_bounded = _instantiate(source, inputs, builder, model, max_visits)
        target_trace, target_bounded = _instantiate(target, inputs, builder, model, max_visits)
        bounded = bounded or source_bounded or target_bounded
        source_traces.append(source_trace)
        target_traces.append(target_trace)
        traces += [source_trace, target_trace]

    for axiom in _hole_congruence(builder, traces):
        builder.insert(smt.AssertOp(axiom))

    same_source = _traces_agree(builder, source_traces[0], source_traces[1])
    same_target = _traces_agree(builder, target_traces[0], target_traces[1])
    differs = builder.insert(smt.NotOp(same_target)).result
    builder.insert(smt.AssertOp(builder.insert(smt.AndOp(same_source, differs)).result))
    builder.insert(smt.CheckSatOp())

    LowerEffectPass().apply(ctx, module)
    SMTExpand().apply(ctx, module)
    if opt:
        LowerPairs().apply(ctx, module)
        CanonicalizePass().apply(ctx, module)
        CommonSubexpressionElimination().apply(ctx, module)
        CanonicalizePass().apply(ctx, module)
        DeadCodeElimination().apply(ctx, module)
    module.verify()

    stream = StringIO()
    print_to_smtlib(module, stream)
    return (
        stream.getvalue(),
        len(source_traces[0].observations),
        len(target_traces[0].observations),
        bounded,
    )


def _run_z3(script: str, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["z3", "-in", f"-T:{timeout}"],
        capture_output=True,
        input=script,
        text=True,
        check=False,
    )


def check_lowering(
    ctx: Context,
    template: ModuleOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    timeout: int = 60,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> LoweringResult:
    """Decide whether a structural lowering specification preserves constant-time."""
    try:
        script, n_source, n_target, bounded = build_query(ctx, template, model, opt, max_visits)
    except Exception as e:
        return LoweringResult("unknown", 0, 0, "", reason=f"{type(e).__name__}: {e}")

    result = _run_z3(script, timeout)
    output = result.stdout.strip()
    if output.startswith("unsat"):
        return LoweringResult("ct-preserving", n_source, n_target, script, output, bounded=bounded)
    if output.startswith("sat"):
        with_model = _run_z3(script + "\n(get-model)\n", timeout)
        return LoweringResult(
            "ct-breaking",
            n_source,
            n_target,
            script,
            output,
            with_model.stdout.strip(),
            bounded=bounded,
        )
    return LoweringResult(
        "unknown",
        n_source,
        n_target,
        script,
        output,
        reason=f"solver said {output or '<nothing>'}; stderr: {result.stderr.strip()}",
        bounded=bounded,
    )
