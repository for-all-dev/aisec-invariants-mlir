"""Turn a control-flow program into a guarded straight-line one.

FCVD lowers single-block regions only, which is why the earlier note called control
flow the expensive part. It is expensive to *model faithfully*, not to represent: an
acyclic CFG can be flattened by if-conversion -- execute everything, select at the
merge points -- and the control flow that mattered for security survives as explicit
`fcvd.observe` operations carrying the guard under which each observation happens.

That is what this module does, for `scf.if` and for acyclic `cf` graphs. Loops are
rejected rather than approximated: a wrong answer about a loop is worse than no answer.

The guard matters. Under if-conversion both branches are evaluated, so recording their
observations unconditionally would credit the source program with leaking more than it
does -- and since the source's leakage is the assumption side of the property, that
would silently turn breaking rewrites into passing ones. Every observation therefore
carries the path condition it happens under, and traces are compared as
`same guards /\\ (guard -> same value)`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from xdsl.dialects import arith, cf, func, scf
from xdsl.dialects.builtin import IntegerAttr, IntegerType
from xdsl.ir import Block, Operation, SSAValue

from .dialect import HoleOp, ObserveOp
from .leakage import DEFAULT_MODEL, LeakageRule

I1 = IntegerType(1)


class UnsupportedTemplate(Exception):
    """The template uses control flow this encoder does not model."""


@dataclass
class Flattener:
    """Builds one straight-line block out of a function body."""

    model: dict[type[Operation], LeakageRule]
    out: Block = field(default_factory=Block)

    def emit(self, op: Operation) -> Operation:
        self.out.add_op(op)
        return op

    def constant_true(self) -> SSAValue:
        return self.emit(arith.ConstantOp(IntegerAttr(1, I1), I1)).results[0]

    def negate(self, value: SSAValue) -> SSAValue:
        return self.emit(arith.XOrIOp(value, self.constant_true())).results[0]

    def conjoin(self, lhs: SSAValue, rhs: SSAValue) -> SSAValue:
        return self.emit(arith.AndIOp(lhs, rhs)).results[0]

    def disjoin(self, lhs: SSAValue, rhs: SSAValue) -> SSAValue:
        return self.emit(arith.OrIOp(lhs, rhs)).results[0]

    def select(self, cond: SSAValue, on_true: SSAValue, on_false: SSAValue) -> SSAValue:
        return self.emit(arith.SelectOp(cond, on_true, on_false)).results[0]

    def observe(self, guard: SSAValue, value: SSAValue) -> None:
        self.emit(ObserveOp(operands=[guard, value], result_types=[]))

    def move(self, op: Operation, guard: SSAValue) -> None:
        """Move one operation into the output block, recording what it leaks."""
        if isinstance(op, scf.IfOp):
            self.expand_if(op, guard)
            return
        if isinstance(op, scf.ForOp | scf.WhileOp):
            raise UnsupportedTemplate(f"loops are not modelled yet: {op.name}")

        op.detach()
        self.out.add_op(op)

        if isinstance(op, HoleOp):
            leaks = op.leaks.value.data
            if leaks:
                for leaked in op.results[len(op.results) - leaks :]:
                    self.observe(guard, leaked)
            return
        rule = self.model.get(type(op))
        if rule is not None:
            for observed in rule(op.operands):
                self.observe(guard, observed)

    def expand_if(self, op: scf.IfOp, guard: SSAValue) -> None:
        # The branch condition is observable: taking one arm rather than the other is
        # exactly what an attacker watching control flow sees.
        self.observe(guard, op.cond)
        then_results = self.inline(op.true_region.block, self.conjoin(guard, op.cond))
        else_guard = self.conjoin(guard, self.negate(op.cond))
        else_results = (
            self.inline(op.false_region.block, else_guard) if op.false_region.blocks else ()
        )
        for index, result in enumerate(op.results):
            merged = self.select(op.cond, then_results[index], else_results[index])
            result.replace_by(merged)
        op.detach()
        op.erase()

    def inline(self, block: Block, guard: SSAValue) -> tuple[SSAValue, ...]:
        """Move a region's single block in under `guard`, returning its yielded values."""
        yielded: tuple[SSAValue, ...] = ()
        for op in list(block.ops):
            if isinstance(op, scf.YieldOp):
                yielded = tuple(op.operands)
                continue
            self.move(op, guard)
        return yielded


def _topological_blocks(blocks: Sequence[Block]) -> list[Block]:
    """Blocks in an order where every predecessor comes first; cycles are rejected."""
    remaining = list(blocks)
    ordered: list[Block] = []
    placed: set[Block] = set()
    while remaining:
        progressed = False
        for block in list(remaining):
            preds = set(block.predecessors())
            if preds <= placed:
                ordered.append(block)
                placed.add(block)
                remaining.remove(block)
                progressed = True
        if not progressed:
            raise UnsupportedTemplate(
                "the control-flow graph has a cycle; loops are not modelled yet"
            )
    return ordered


def flatten(
    function: func.FuncOp,
    model: dict[type[Operation], LeakageRule] | None = None,
) -> Block:
    """If-convert a function body into a single guarded straight-line block."""
    flattener = Flattener(DEFAULT_MODEL if model is None else model)
    body = function.body
    entry = body.blocks[0]

    out = flattener.out
    for arg in list(entry.args):
        new_arg = out.insert_arg(arg.type, len(out.args))
        arg.replace_by(new_arg)

    # (condition, arguments) of every edge reaching a block, filled in as we go.
    incoming: dict[Block, list[tuple[SSAValue, Sequence[SSAValue]]]] = {}
    guards: dict[Block, SSAValue] = {}

    for block in _topological_blocks(list(body.blocks)):
        if block is entry:
            guards[block] = flattener.constant_true()
        else:
            edges = incoming.get(block, [])
            if not edges:
                continue  # unreachable block: nothing it does can be observed
            guard = edges[0][0]
            for condition, _ in edges[1:]:
                guard = flattener.disjoin(guard, condition)
            guards[block] = guard
            for index, arg in enumerate(list(block.args)):
                merged = edges[0][1][index]
                for condition, arguments in edges[1:]:
                    merged = flattener.select(condition, arguments[index], merged)
                arg.replace_by(merged)

        guard = guards[block]
        for op in list(block.ops):
            if isinstance(op, cf.BranchOp):
                incoming.setdefault(op.successors[0], []).append((guard, list(op.arguments)))
            elif isinstance(op, cf.ConditionalBranchOp):
                flattener.observe(guard, op.cond)
                incoming.setdefault(op.then_block, []).append(
                    (flattener.conjoin(guard, op.cond), list(op.then_arguments))
                )
                incoming.setdefault(op.else_block, []).append(
                    (
                        flattener.conjoin(guard, flattener.negate(op.cond)),
                        list(op.else_arguments),
                    )
                )
            elif isinstance(op, func.ReturnOp):
                # Results are irrelevant here: the property is about observations.
                continue
            elif isinstance(op, cf.SwitchOp | cf.AssertOp):
                raise UnsupportedTemplate(f"not modelled yet: {op.name}")
            else:
                flattener.move(op, guard)

    return out
