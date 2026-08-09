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

That is one half of what a lowering has to get right. The other half is that it still
computes the same thing, and the leakage property cannot see it: a rewrite that returns
a stale value adds no observation, so it passes. `check_equivalence` asks the second
question on the same machinery -- same flattening, same holes, same congruence axioms,
but comparing the values the two programs *return* and the memory they leave behind
instead of their observation traces -- and `check_template` is the gate that requires
both answers. Upstream's refinement criterion is the one mirrored here, UB polarity
included (`ub_source \/ (not ub_target /\ values agree)`), so a source that is already
undefined excuses the target, exactly as in `pdl_to_smt`.
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
from xdsl.dialects.func import FuncOp
from xdsl.ir import Operation, SSAValue
from xdsl.rewriter import InsertPoint
from xdsl_smt.dialects import smt_dialect as smt
from xdsl_smt.dialects import smt_utils_dialect as smt_utils
from xdsl_smt.dialects.effects import ub_effect
from xdsl_smt.dialects.effects.effect import StateType
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.traits.smt_printer import print_to_smtlib

from .dialect import StructuralTrace
from .leakage import LeakageRule
from .predication import DEFAULT_MAX_VISITS, UnsupportedTemplate
from .smtutil import as_bool, finish_module, instantiate, observed_value, traces_agree
from .smtutil import conjoin as _conjoin

Verdict = Literal["ct-preserving", "ct-breaking", "unknown"]
EquivalenceVerdict = Literal["equivalent", "not-equivalent", "unknown"]
GateVerdict = Literal["verified", "rejected", "unknown"]


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


@dataclass
class EquivalenceResult:
    verdict: EquivalenceVerdict
    n_compared: int
    """How many returned values were related. Zero means the template returns nothing,
    and then `equivalent` rests on the memory clause alone -- printed, so the two are
    not read alike."""
    reached_return: bool = True
    """False when no path reached a `func.return`, which makes the value clause vacuous."""
    smtlib: str = ""
    solver_output: str = ""
    counterexample: str = ""
    reason: str = ""
    bounded: bool = False
    memory_compared: bool = True
    """False when the template declared `fcvdct.values_only`: the verdict rests on the
    returned values alone."""


@dataclass
class GateResult:
    """Both halves of "the lowering is safe", and the verdict that needs both."""

    verdict: GateVerdict
    constant_time: LoweringResult
    equivalence: EquivalenceResult

    @property
    def reason(self) -> str:
        return "; ".join(
            part for part in (self.constant_time.reason, self.equivalence.reason) if part
        )


def _hole_congruence(
    builder: Builder, traces: Sequence[StructuralTrace], exact: bool = False
) -> list[SSAValue]:
    """Equal inputs give equal outputs, for every pair of occurrences of a hole.

    `exact` relates the whole lowered value, definedness included, rather than only the
    value component. The leakage query wants the weak form and says why below. The
    equivalence query wants this one: two runs of the same code on the same input are
    either both defined or both not, and if the outputs' poison bits are left free, a
    *correct* rewrite is refuted -- the accumulated result inherits a poison marker in one
    program that it does not have in the other. Safe here and not in the leakage query
    because that one cannot assume anything about its inputs, while this one asserts they
    are defined, which is what kept the poison out of the unrolling `select`s.
    """
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

                # Compare the values, not the poison bits. `traces_agree` already made
                # that call for observations, and a hole models code the attacker
                # cannot see into: it can no more observe definedness than the trace
                # can. Comparing raw pairs makes congruence fail whenever a poison
                # marker differs -- which is what a loop does as soon as its bound is
                # a function argument, since the unrolled `select` inherits that
                # poison. The result was a *correct* rewrite reported as ct-breaking.
                def same(
                    left: Sequence[SSAValue], right: Sequence[SSAValue], exact: bool = exact
                ) -> SSAValue:
                    return _conjoin(
                        builder,
                        [
                            builder.insert(
                                smt.EqOp(one, other)
                                if exact
                                else smt.EqOp(
                                    observed_value(builder, one), observed_value(builder, other)
                                )
                            ).res
                            for one, other in zip(left, right, strict=True)
                        ],
                    )

                same_inputs = same(inputs, other_inputs)
                same_outputs = same(outputs, other_outputs)
                axioms.append(builder.insert(smt.ImpliesOp(same_inputs, same_outputs)).result)
    return axioms


def _instantiate(
    function: FuncOp,
    inputs: Sequence[SSAValue],
    block_builder: Builder,
    model: dict[type[Operation], LeakageRule] | None,
    max_visits: int,
    state: SSAValue | None = None,
) -> tuple[StructuralTrace, bool]:
    """Flatten one program and lower it to SMT from the given initial effect state.

    The initial memory is an *input*: the source and target of one run must read the
    same one, or a program that loads from memory can never be proved preserving (the
    identity template itself came back ct-breaking until 2026-08-09, which is how this
    was found). Only the initial state is shared -- each program threads its own state
    chain from there, so UB raised by one still cannot propagate into another.
    """
    trace, bounded, _ = instantiate(function, inputs, block_builder, model, max_visits, state)
    return trace, bounded


def _two_functions(template: ModuleOp) -> tuple[FuncOp, FuncOp]:
    """The `@source` and `@target` of a template, checked to be comparable at all."""
    functions = {op.sym_name.data: op for op in template.body.ops if isinstance(op, FuncOp)}
    if set(functions) != {"source", "target"}:
        raise UnsupportedTemplate(
            "a template must contain exactly two functions, @source and @target, "
            f"found {sorted(functions)}"
        )
    source, target = functions["source"], functions["target"]
    if source.function_type.inputs != target.function_type.inputs:
        raise UnsupportedTemplate("@source and @target must take the same inputs")
    return source, target


def build_query(
    ctx: Context,
    template: ModuleOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> tuple[str, int, int, bool]:
    """Build the SMTLib script asserting that the lowering *breaks* constant-time."""
    source, target = _two_functions(template)

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
        # Source and target of one run see the same inputs -- the initial memory
        # included; the two runs do not.
        state = builder.insert(smt.DeclareConstOp(StateType())).res
        state.name_hint = f"memory_in_run{run}"
        source_trace, source_bounded = _instantiate(
            source, inputs, builder, model, max_visits, state
        )
        target_trace, target_bounded = _instantiate(
            target, inputs, builder, model, max_visits, state
        )
        bounded = bounded or source_bounded or target_bounded
        source_traces.append(source_trace)
        target_traces.append(target_trace)
        traces += [source_trace, target_trace]

    for axiom in _hole_congruence(builder, traces):
        builder.insert(smt.AssertOp(axiom))

    same_source = traces_agree(
        builder, source_traces[0].observations, source_traces[1].observations
    )
    same_target = traces_agree(
        builder, target_traces[0].observations, target_traces[1].observations
    )
    differs = builder.insert(smt.NotOp(same_target)).result
    builder.insert(smt.AssertOp(builder.insert(smt.AndOp(same_source, differs)).result))
    builder.insert(smt.CheckSatOp())

    finish_module(ctx, module, opt)

    stream = StringIO()
    print_to_smtlib(module, stream)
    return (
        stream.getvalue(),
        len(source_traces[0].observations),
        len(target_traces[0].observations),
        bounded,
    )


def _poison_of(builder: Builder, value: SSAValue) -> SSAValue | None:
    """The definedness marker of a lowered value, if it carries one."""
    if isinstance(value.type, smt_utils.PairType) and isinstance(value.type.second, smt.BoolType):
        return builder.insert(smt_utils.SecondOp(value)).res
    return None


def _value_refinement(builder: Builder, before: SSAValue, after: SSAValue) -> SSAValue:
    """`not poison_before -> (values equal /\\ not poison_after)`.

    Upstream's `IntegerTypeRefinementSemantics`, rebuilt here because ours relates values
    inside one module rather than the results of two `smt.define_fun`s. A poisoned source
    value may become anything, which is what makes this a refinement and not equality.
    """
    equal = builder.insert(
        smt.EqOp(observed_value(builder, before), observed_value(builder, after))
    ).res
    after_poison = _poison_of(builder, after)
    if after_poison is not None:
        not_after = builder.insert(smt.NotOp(after_poison)).result
        equal = builder.insert(smt.AndOp(equal, not_after)).result
    before_poison = _poison_of(builder, before)
    if before_poison is not None:
        not_before = builder.insert(smt.NotOp(before_poison)).result
        return builder.insert(smt.ImpliesOp(not_before, equal)).result
    return equal


def build_equivalence_query(
    ctx: Context,
    template: ModuleOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    max_visits: int = DEFAULT_MAX_VISITS,
    assume_defined_inputs: bool = True,
    compare_memory: bool = True,
) -> tuple[str, int, bool, bool]:
    """Build the SMTLib script asserting that the lowering *changes what is computed*.

    Two programs, not four: equivalence relates the source and the target on one input,
    where constant-time relates one program to itself on two. They share the inputs *and*
    the initial memory, since a target that starts from a different heap could not be
    compared to anything.
    """
    source, target = _two_functions(template)
    if source.function_type.outputs != target.function_type.outputs:
        raise UnsupportedTemplate("@source and @target must return the same types")

    module = ModuleOp([])
    builder = Builder(InsertPoint.at_end(module.body.block))

    inputs: list[SSAValue] = []
    for index, input_type in enumerate(source.function_type.inputs):
        declared = builder.insert(smt.DeclareConstOp(SMTLowerer.lower_type(input_type)))
        declared.res.name_hint = f"in{index}"
        inputs.append(declared.res)
        # The arguments are defined -- `assume_defined_inputs`, on unless a test turns it
        # off to show the assumption is load-bearing. Without it the query answers a
        # different question:
        # a free input carries a free poison bit, an operation that refuses poison raises
        # UB on it, and a target that guards its divisor is then reported as changing the
        # meaning of a source that never had one. This is the P0 finding of
        # `docs/research/fcvd-selfcomposition.agents.md` arriving through the UB clause
        # instead of the value one -- the leakage query never met it, because it compares
        # value components and ignores definedness.
        poison = _poison_of(builder, declared.res) if assume_defined_inputs else None
        if poison is not None:
            builder.insert(smt.AssertOp(builder.insert(smt.NotOp(poison)).result))
    state = builder.insert(smt.DeclareConstOp(StateType())).res
    state.name_hint = "memory_in"

    source_trace, source_bounded, source_state = instantiate(
        source, inputs, builder, model, max_visits, state
    )
    target_trace, target_bounded, target_state = instantiate(
        target, inputs, builder, model, max_visits, state
    )
    assert source_state is not None and target_state is not None
    bounded = source_bounded or target_bounded

    for axiom in _hole_congruence(builder, [source_trace, target_trace], exact=True):
        builder.insert(smt.AssertOp(axiom))

    # A path is identified by its guard, so "the two programs returned the same thing"
    # is: wherever a source path and a target path are both taken, their results agree.
    # Pairing by index would be wrong -- the target's CFG has its own shape, and after
    # unrolling its return sites need not line up with the source's.
    terms: list[SSAValue] = []
    n_compared = 0
    for source_site in source_trace.results:
        for target_site in target_trace.results:
            if len(source_site.values) != len(target_site.values):
                raise UnsupportedTemplate("a return site returns the wrong number of values")
            both_taken = builder.insert(
                smt.AndOp(as_bool(builder, source_site.guard), as_bool(builder, target_site.guard))
            ).result
            agree = _conjoin(
                builder,
                [
                    _value_refinement(builder, before, after)
                    for before, after in zip(source_site.values, target_site.values, strict=True)
                ],
            )
            terms.append(builder.insert(smt.ImpliesOp(both_taken, agree)).result)
            n_compared += len(source_site.values)

    # The memory the two programs leave behind, compared whole. This is stronger than
    # upstream's block-by-block refinement -- it also pins the unallocated part and the
    # order blocks were allocated in -- so it can raise a false alarm on a lowering that
    # reallocates, and cannot pass one that writes different bytes. Strict is the safe
    # direction for a gate, and the asymmetry is reported rather than assumed away.
    ub_source = builder.insert(ub_effect.ToBoolOp(source_state)).res
    ub_target = builder.insert(ub_effect.ToBoolOp(target_state)).res
    not_ub_target = builder.insert(smt.NotOp(ub_target)).result
    memory_clause: list[SSAValue] = []
    if compare_memory:
        memory_clause.append(builder.insert(smt.EqOp(source_state, target_state)).res)
    defined_case = _conjoin(builder, [not_ub_target, *memory_clause, *terms])
    refines = builder.insert(smt.OrOp(ub_source, defined_case)).result

    builder.insert(smt.AssertOp(builder.insert(smt.NotOp(refines)).result))
    builder.insert(smt.CheckSatOp())

    finish_module(ctx, module, opt)

    stream = StringIO()
    print_to_smtlib(module, stream)
    return stream.getvalue(), n_compared, bounded, bool(source_trace.results)


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


VALUES_ONLY_ATTR = "fcvdct.values_only"
"""A template carrying this module attribute asks the equivalence gate to compare the
returned values but not the final memory. The whole-state comparison is strict enough to
refuse any step that legitimately *removes* allocations (mem2reg being the canonical
one) -- the docstring of `build_equivalence_query` warns of exactly this false alarm.
The weakening is declared in the template file itself, so it is visible next to the
transcription it excuses, and it is printed with the verdict."""


def values_only(template: ModuleOp) -> bool:
    return VALUES_ONLY_ATTR in (template.attributes or {})


def check_equivalence(
    ctx: Context,
    template: ModuleOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    timeout: int = 60,
    max_visits: int = DEFAULT_MAX_VISITS,
    assume_defined_inputs: bool = True,
) -> EquivalenceResult:
    """Decide whether the target of a lowering computes what the source computed."""
    skip_memory = values_only(template)
    try:
        script, n_compared, bounded, reached = build_equivalence_query(
            ctx,
            template,
            model,
            opt,
            max_visits,
            assume_defined_inputs,
            compare_memory=not skip_memory,
        )
    except Exception as e:
        return EquivalenceResult("unknown", 0, reason=f"{type(e).__name__}: {e}")

    result = _run_z3(script, timeout)
    output = result.stdout.strip()
    if output.startswith("unsat"):
        return EquivalenceResult(
            "equivalent",
            n_compared,
            reached,
            script,
            output,
            bounded=bounded,
            memory_compared=not skip_memory,
            reason=(
                "values only: the memory clause is OFF by the template's own declaration"
                if skip_memory
                else ("" if reached else "no path reached a return: values were not compared")
            ),
        )
    if output.startswith("sat"):
        with_model = _run_z3(script + "\n(get-model)\n", timeout)
        return EquivalenceResult(
            "not-equivalent",
            n_compared,
            reached,
            script,
            output,
            with_model.stdout.strip(),
            bounded=bounded,
            memory_compared=not skip_memory,
        )
    return EquivalenceResult(
        "unknown",
        n_compared,
        reached,
        script,
        output,
        reason=f"solver said {output or '<nothing>'}; stderr: {result.stderr.strip()}",
        bounded=bounded,
        memory_compared=not skip_memory,
    )


def check_template(
    ctx: Context,
    template: ModuleOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    opt: bool = True,
    timeout: int = 60,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> GateResult:
    """The gate: a lowering is verified only if it preserves constant-time *and* meaning.

    Neither half implies the other. A rewrite that returns a stale value adds no
    observation, so the leakage query passes it; a rewrite that branches on a secret
    computes exactly the right answer, so the equivalence query passes it. Both are
    reported, and `verified` requires both.
    """
    ct = check_lowering(ctx, template, model, opt, timeout, max_visits)
    equivalence = check_equivalence(ctx, template, model, opt, timeout, max_visits)
    if ct.verdict == "unknown" or equivalence.verdict == "unknown":
        return GateResult("unknown", ct, equivalence)
    if ct.verdict == "ct-preserving" and equivalence.verdict == "equivalent":
        return GateResult("verified", ct, equivalence)
    return GateResult("rejected", ct, equivalence)
