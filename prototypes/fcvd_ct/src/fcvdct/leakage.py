"""The leakage model: what an attacker observes, and how we capture it.

FCVD's semantics describe values, memory and UB -- never an observation trace, so
constant-time is not expressible in them as they stand. This module adds the missing
half: a table saying which operations are observable and which of their operands the
observation consists of, plus a recorder that captures those operands as SMT values
while the program is being lowered to SMT.

Capturing at lowering time (rather than instrumenting the MLIR beforehand) is what
makes this usable from `pdl-to-smt`, where the "program" is a symbolic pattern that
never exists as concrete IR.

Every verdict this package produces is relative to the model chosen here. The default
model mirrors the one layer A (binsec `ct`) uses on binaries, so the two layers make
comparable statements: variable-latency integer division leaks its operands, memory
accesses leak their addresses, everything else is assumed constant-time.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

from xdsl.dialects import arith, llvm, memref, tensor
from xdsl.ir import Attribute, Operation, SSAValue
from xdsl.pattern_rewriter import PatternRewriter
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer
from xdsl_smt.semantics.semantics import OperationSemantics

from .dialect import ADDRESS, CONTROL, LATENCY, RESOURCE

# A leakage rule maps the operands of an operation to the observations it emits.
Selector = Callable[[Sequence[SSAValue]], Sequence[SSAValue]]


@dataclass(frozen=True)
class Rule:
    """Which operands of an operation leak, and which obligation the leak belongs to."""

    kind: str
    select: Selector

    def __call__(self, values: Sequence[SSAValue]) -> Sequence[SSAValue]:
        return self.select(values)


LeakageRule = Rule


def operands(*indices: int) -> Selector:
    """Observe the operands at the given positions."""

    def rule(values: Sequence[SSAValue]) -> Sequence[SSAValue]:
        return [values[i] for i in indices]

    return rule


def operands_from(start: int) -> Selector:
    """Observe every operand from `start` onwards (memref indices, for instance)."""

    def rule(values: Sequence[SSAValue]) -> Sequence[SSAValue]:
        return list(values[start:])

    return rule


#: Integer division and remainder are the variable-latency instructions on the
#: targets we care about: x86 `idiv`/`div` latency depends on both operands. Shifts,
#: multiplies and boolean ops are constant-latency and are deliberately absent.
VARIABLE_LATENCY_RULES: dict[type[Operation], LeakageRule] = {
    arith.DivSIOp: Rule(LATENCY, operands(0, 1)),
    arith.DivUIOp: Rule(LATENCY, operands(0, 1)),
    arith.RemSIOp: Rule(LATENCY, operands(0, 1)),
    arith.RemUIOp: Rule(LATENCY, operands(0, 1)),
    arith.CeilDivSIOp: Rule(LATENCY, operands(0, 1)),
    arith.CeilDivUIOp: Rule(LATENCY, operands(0, 1)),
    arith.FloorDivSIOp: Rule(LATENCY, operands(0, 1)),
}

#: A memory access leaks the address it touches, which is the cache-line channel that
#: `mlir_leak` found empirically in the sparsifier.
ADDRESS_RULES: dict[type[Operation], LeakageRule] = {
    memref.LoadOp: Rule(ADDRESS, operands_from(1)),
    memref.StoreOp: Rule(ADDRESS, operands_from(2)),
    # A tensor is not memory yet, but it becomes memory: HEIR bufferizes before its
    # backend, and an extraction at a secret index is exactly what its data-oblivious
    # passes exist to remove. See `tensor_ops.py` for the assumption in full.
    tensor.ExtractOp: Rule(ADDRESS, operands_from(1)),
    tensor.InsertOp: Rule(ADDRESS, operands_from(2)),
    # After memref is lowered C-style, the address is a getelementptr and the access is
    # an llvm.load/store on its result. The index operands of the GEP are what a memref
    # access leaked before lowering, so leaking them here keeps the two comparable --
    # the load/store themselves take an already-computed pointer and add no new secret.
    llvm.GEPOp: Rule(ADDRESS, operands_from(1)),
}

#: The resource obligation of the plan -- "the sets of allocated and un-freed memory at
#: the end are identical". A dynamic allocation leaks its size; a `dealloc` leaks which
#: block it releases, so a secret-dependent choice of block cannot pass unnoticed.
RESOURCE_RULES: dict[type[Operation], LeakageRule] = {
    memref.AllocOp: Rule(RESOURCE, operands_from(0)),
    memref.AllocaOp: Rule(RESOURCE, operands_from(0)),
    memref.DeallocOp: Rule(RESOURCE, operands(0)),
}

DEFAULT_MODEL: dict[type[Operation], LeakageRule] = {
    **VARIABLE_LATENCY_RULES,
    **ADDRESS_RULES,
    **RESOURCE_RULES,
}

#: Control-flow observations are emitted by the flattener rather than by an operation
#: rule (a branch has no operand that "is" the leak -- the condition is the leak), so
#: this constant only records that the kind belongs to the same model.
CONTROL_KIND = CONTROL


@dataclass
class LeakageTrace:
    """The observations of one lowering run, split by which program they belong to.

    A `pdl.pattern` describes two programs at once. An operation that is matched and
    replaced belongs to the source program only; an operation created by the rewrite
    belongs to the target only; an operation that is matched but left in place is part
    of both, and so is observed by both traces.
    """

    source: list[SSAValue] = field(default_factory=list[SSAValue])
    target: list[SSAValue] = field(default_factory=list[SSAValue])

    def record(self, observations: Sequence[SSAValue], *, in_source: bool, in_target: bool) -> None:
        if in_source:
            self.source.extend(observations)
        if in_target:
            self.target.extend(observations)


@dataclass
class _RecordingSemantics(OperationSemantics):
    """Wraps an operation's semantics so that lowering it also records its leakage."""

    inner: OperationSemantics
    rule: LeakageRule
    trace: LeakageTrace

    def get_semantics(
        self,
        operands: Sequence[SSAValue],
        results: Sequence[Attribute],
        attributes: Mapping[str, Attribute | SSAValue],
        effect_state: SSAValue | None,
        rewriter: PatternRewriter,
    ) -> tuple[Sequence[SSAValue], SSAValue | None]:
        matched = getattr(rewriter, "current_operation", None)
        # `pdl-to-smt` marks which side of the rewrite an operation lives on. Outside
        # of PDL there is a single program, which is both source and target.
        created = matched is not None and "is_created" in matched.attributes
        deleted = matched is not None and "is_deleted" in matched.attributes
        self.trace.record(
            self.rule(operands),
            in_source=not created,
            in_target=not deleted,
        )
        return self.inner.get_semantics(operands, results, attributes, effect_state, rewriter)


@contextmanager
def recording(
    model: dict[type[Operation], LeakageRule] | None = None,
) -> Iterator[LeakageTrace]:
    """Install the leakage model into the SMT lowerer for the duration of the block.

    `SMTLowerer.op_semantics` is global state in xdsl-smt, so it is saved and restored
    rather than mutated in place.
    """
    model = DEFAULT_MODEL if model is None else model
    trace = LeakageTrace()
    saved = SMTLowerer.op_semantics
    wrapped = dict(saved)
    for op_type, rule in model.items():
        if op_type not in saved:
            # An operation we would like to observe has no semantics upstream: lowering
            # a program containing it fails anyway, so there is nothing to wrap.
            continue
        wrapped[op_type] = _RecordingSemantics(saved[op_type], rule, trace)
    SMTLowerer.op_semantics = wrapped
    try:
        yield trace
    finally:
        SMTLowerer.op_semantics = saved
