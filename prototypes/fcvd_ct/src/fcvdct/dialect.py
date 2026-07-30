"""The operations a structural lowering specification is written with.

A lowering like `scf.if` -> `cf.cond_br` is a *template*: it says nothing about the
code inside the branches, and it has to be correct whatever that code is. Two ops are
enough to write such a template down and hand it to a solver:

- `fcvd.hole` stands for "arbitrary code here". It is an uninterpreted function: equal
  inputs give equal results and equal leakage, and nothing else is known about it. The
  trailing `leaks` results are its observations rather than its values.
- `fcvd.observe` marks one observation: a value the attacker learns, and the guard
  under which the program actually reaches it.

A third one is not written by hand. `fcvd.result` is emitted by the flattener wherever
it walks a `func.return`, and it records what the program returns on that path. The
leakage property never looks at it; the equivalence gate does, and both need the values
*after* they have been lowered to SMT, which is why this is an operation with semantics
rather than a list built while flattening.

All three get SMT semantics here, so they lower through FCVD's own machinery like any
other operation.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

from xdsl.dialects.builtin import IntegerAttr, StringAttr
from xdsl.ir import Attribute, Dialect, SSAValue
from xdsl.irdl import (
    IRDLOperation,
    attr_def,
    irdl_op_definition,
    operand_def,
    opt_attr_def,
    var_operand_def,
    var_result_def,
)
from xdsl.pattern_rewriter import PatternRewriter
from xdsl_smt.dialects.smt_dialect import DeclareConstOp
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.semantics.semantics import OperationSemantics


@irdl_op_definition
class HoleOp(IRDLOperation):
    """Arbitrary code. `sym_name` identifies it across the programs of a template.

    The last `leaks` results are the observations the code makes; the ones before them
    are the values it computes.
    """

    name = "fcvd.hole"

    inputs = var_operand_def()
    outputs = var_result_def()

    sym_name = attr_def(StringAttr)
    leaks = attr_def(IntegerAttr)


#: An observation belongs to one of the security obligations. The names are the ones
#: the self-composition driver proves separately, so that a verdict says *which*
#: channel a kernel leaks through rather than only that it does.
CONTROL = "control"
"""Which branch was taken, how many times a loop ran."""
ADDRESS = "address"
"""The address a load or store touched."""
LATENCY = "latency"
"""The operands of a variable-latency instruction."""
RESOURCE = "resource"
"""Allocation sizes and the pointers handed back to `dealloc`."""
OTHER = "other"
"""An observation a template declares itself, with no obligation attached."""


@irdl_op_definition
class ObserveOp(IRDLOperation):
    """`guard` says whether the program reaches this observation; `value` is what leaks.

    `kind` names the obligation the observation belongs to; templates that predate the
    split leave it out and are treated as `other`.
    """

    name = "fcvd.observe"

    guard = operand_def()
    value = operand_def()

    kind = opt_attr_def(StringAttr)


@irdl_op_definition
class ResultOp(IRDLOperation):
    """What the program returns on one path, and the guard under which it goes there.

    A flattened program has one of these per `func.return` the walk reached, so a
    program with branches has several and a program whose paths were all cut by the
    unrolling bound has none. It emits no SMT: like `fcvd.observe` it only records, so
    adding it to a program cannot move a leakage verdict.
    """

    name = "fcvd.result"

    guard = operand_def()
    values = var_operand_def()


FCVD = Dialect("fcvd", [HoleOp, ObserveOp, ResultOp])


@dataclass
class HoleInstance:
    """One occurrence of a hole, in one program of one run."""

    sym_name: str
    inputs: tuple[SSAValue, ...]
    outputs: tuple[SSAValue, ...]


@dataclass
class Observation:
    guard: SSAValue
    value: SSAValue
    kind: str = OTHER


@dataclass
class ResultSite:
    """One `func.return` the flattener reached, with the guard that leads to it."""

    guard: SSAValue
    values: tuple[SSAValue, ...]


@dataclass
class StructuralTrace:
    """What one program of one run computed: observations, holes, and what it returned."""

    observations: list[Observation] = field(default_factory=list[Observation])
    holes: list[HoleInstance] = field(default_factory=list[HoleInstance])
    results: list[ResultSite] = field(default_factory=list[ResultSite])


@dataclass
class HoleSemantics(OperationSemantics):
    """An unconstrained result per output; the congruence axioms are added by the driver.

    Constraining holes here is not possible: the axioms relate instances *across* the
    four programs a check builds, which this callback cannot see.
    """

    trace: StructuralTrace

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        sym_name = attributes["sym_name"]
        assert isinstance(sym_name, StringAttr)
        outputs: list[SSAValue] = []
        for result_type in results:
            declared = DeclareConstOp(SMTLowerer.lower_type(result_type))
            rewriter.insert_op_before_matched_op(declared)
            declared.res.name_hint = f"{sym_name.data}_{len(outputs)}"
            outputs.append(declared.res)
        self.trace.holes.append(HoleInstance(sym_name.data, tuple(operands), tuple(outputs)))
        return outputs, effect_state


@dataclass
class ObserveSemantics(OperationSemantics):
    trace: StructuralTrace

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        guard, value = operands
        kind = attributes.get("kind")
        self.trace.observations.append(
            Observation(guard, value, kind.data if isinstance(kind, StringAttr) else OTHER)
        )
        return (), effect_state


@dataclass
class ResultSemantics(OperationSemantics):
    trace: StructuralTrace

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        guard, *values = operands
        self.trace.results.append(ResultSite(guard, tuple(values)))
        return (), effect_state


@contextmanager
def template_semantics(trace: StructuralTrace) -> Iterator[None]:
    """Give the `fcvd` operations semantics for the duration of one lowering.

    `SMTLowerer.op_semantics` is global state upstream, so it is saved and restored
    rather than mutated in place.
    """
    saved = SMTLowerer.op_semantics
    SMTLowerer.op_semantics = {
        **saved,
        HoleOp: HoleSemantics(trace),
        ObserveOp: ObserveSemantics(trace),
        ResultOp: ResultSemantics(trace),
    }
    try:
        yield
    finally:
        SMTLowerer.op_semantics = saved
