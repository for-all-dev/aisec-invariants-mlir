"""Turn a control-flow program into a guarded straight-line one, loops included.

FCVD's operation translation is exact on straight-line code and on `if`, and blind on
loops: it cannot walk a back edge a symbolic number of times. This module removes that
blindness the cheap way -- it unrolls.

The walk is a bounded symbolic execution over blocks. Every visit of a block carries
its own path condition and its own copy of the operations, so nothing has to be merged
at joins and a loop header simply gets visited again, up to `max_visits` times. An
acyclic diamond comes out as both arms under their guards; a loop comes out as
`max_visits` guarded copies of its body. Paths that still have work left when the
budget runs out are cut, and the caller is told, because a verdict that only holds for
the first few iterations must not be reported as if it held for all of them.

Guards are the part that has to be right. Both arms of a branch are present in the
flattened program, so an observation records the path condition it happens under, and
traces are compared as `same guards /\\ (guard -> same value)`. Without that, a
program would look like it leaks what it never executes -- and since the source's
leakage is the assumption side of the property, that silently turns real leaks into
passing verdicts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from xdsl.dialects import affine, arith, cf, func, scf
from xdsl.dialects.builtin import IndexType, IntegerAttr, IntegerType, StringAttr
from xdsl.ir import Block, Operation, SSAValue

from .affine_ops import constant_bound
from .dialect import CONTROL, OTHER, HoleOp, ObserveOp, ResultOp
from .leakage import DEFAULT_MODEL, LeakageRule

I1 = IntegerType(1)

DEFAULT_MAX_VISITS = 4
"""How many times one block may be entered on a path -- i.e. the unrolling bound."""


class UnsupportedTemplate(Exception):
    """The program uses a construct this encoder does not model."""


@dataclass
class Flattener:
    """Walks every path of a function, emitting one guarded straight-line block."""

    model: dict[type[Operation], LeakageRule]
    max_visits: int = DEFAULT_MAX_VISITS
    out: Block = field(default_factory=Block)
    hit_bound: bool = False
    """Set when a path was cut because the unrolling bound ran out."""

    # ---- small emitters -------------------------------------------------------

    def emit(self, op: Operation) -> Operation:
        self.out.add_op(op)
        return op

    def constant_true(self) -> SSAValue:
        return self.emit(arith.ConstantOp(IntegerAttr(1, I1), I1)).results[0]

    def negate(self, value: SSAValue) -> SSAValue:
        return self.emit(arith.XOrIOp(value, self.constant_true())).results[0]

    def conjoin(self, lhs: SSAValue, rhs: SSAValue) -> SSAValue:
        return self.emit(arith.AndIOp(lhs, rhs)).results[0]

    def observe(self, guard: SSAValue, value: SSAValue, kind: str = OTHER) -> None:
        self.emit(
            ObserveOp(
                operands=[guard, value],
                result_types=[],
                attributes={"kind": StringAttr(kind)},
            )
        )

    def record_result(self, guard: SSAValue, values: Sequence[SSAValue]) -> None:
        self.emit(ResultOp(operands=[guard, list(values)], result_types=[]))

    # ---- operations -----------------------------------------------------------

    def run_op(self, op: Operation, guard: SSAValue, values: dict[SSAValue, SSAValue]) -> None:
        """Emit a copy of `op` under `guard`, mapping its operands through `values`."""
        if isinstance(op, scf.IfOp):
            self.run_if(op, guard, values)
            return
        if isinstance(op, scf.ForOp):
            self.run_for(op, guard, values)
            return
        if isinstance(op, affine.ForOp):
            self.run_affine_for(op, guard, values)
            return
        if isinstance(op, scf.WhileOp | scf.ParallelOp):
            raise UnsupportedTemplate(f"not modelled yet: {op.name}")

        copy = op.clone(value_mapper=dict(values))
        for original, new in zip(op.results, copy.results, strict=True):
            values[original] = new
        self.emit(copy)

        if isinstance(copy, HoleOp):
            leaks = copy.leaks.value.data
            for leaked in copy.results[len(copy.results) - leaks :] if leaks else ():
                self.observe(guard, leaked)
            return
        rule = self.model.get(type(copy))
        if rule is not None:
            for observed in rule(copy.operands):
                self.observe(guard, observed, rule.kind)

    def run_if(self, op: scf.IfOp, guard: SSAValue, values: dict[SSAValue, SSAValue]) -> None:
        condition = values.get(op.cond, op.cond)
        # Which arm is taken is exactly what an attacker watching control flow sees.
        self.observe(guard, condition, CONTROL)
        then_values = dict(values)
        then_results = self.run_block(
            op.true_region.block, self.conjoin(guard, condition), then_values
        )
        else_guard = self.conjoin(guard, self.negate(condition))
        if op.false_region.blocks:
            else_values = dict(values)
            else_results = self.run_block(op.false_region.block, else_guard, else_values)
        else:
            else_results = ()
        for index, result in enumerate(op.results):
            values[result] = self.emit(
                arith.SelectOp(condition, then_results[index], else_results[index])
            ).results[0]

    def run_for(self, op: scf.ForOp, guard: SSAValue, values: dict[SSAValue, SSAValue]) -> None:
        """Unroll a `scf.for`, guarding iteration *k* by `lb + k*step < ub`.

        The comparison is emitted even when it is trivially true, because how many
        times the loop runs is observable, and that is the loop-bound channel.
        """
        lower = values.get(op.lb, op.lb)
        upper = values.get(op.ub, op.ub)
        step = values.get(op.step, op.step)
        carried = [values.get(arg, arg) for arg in op.iter_args]
        induction = lower

        for _ in range(self.max_visits):
            keep_going = self.emit(arith.CmpiOp(induction, upper, "slt")).results[0]
            self.observe(guard, keep_going, CONTROL)
            iteration_guard = self.conjoin(guard, keep_going)

            body_values = dict(values)
            body = op.body.block
            body_values[body.args[0]] = induction
            for arg, value in zip(body.args[1:], carried, strict=True):
                body_values[arg] = value
            yielded = self.run_block(body, iteration_guard, body_values)

            # Values leaving the loop are the new ones if the iteration ran, the old
            # ones otherwise -- the same shape the `cf` skeleton produces at its join.
            carried = [
                self.emit(arith.SelectOp(keep_going, new, old)).results[0]
                for new, old in zip(yielded, carried, strict=True)
            ]
            induction = self.emit(arith.AddiOp(induction, step)).results[0]

        # One more comparison: if it can still be true, the loop was cut short.
        self.observe(guard, self.emit(arith.CmpiOp(induction, upper, "slt")).results[0], CONTROL)
        self.hit_bound = True

        for result, value in zip(op.results, carried, strict=True):
            values[result] = value

    def run_affine_for(
        self, op: affine.ForOp, guard: SSAValue, values: dict[SSAValue, SSAValue]
    ) -> None:
        """Fully unroll an `affine.for` with constant bounds.

        This is not the same situation as `scf.for`, and the difference is the whole
        point of HEIR's hardening passes: the bounds here are *constants in the map*, so
        the trip count is public. Nothing about it is observed, and because the loop is
        unrolled completely rather than up to a budget, the verdict is exact rather than
        bounded -- provided the trip count fits in `max_visits`, which is checked.
        """
        lower = None if op.lowerBoundOperands else constant_bound(op.lowerBoundMap)
        upper = None if op.upperBoundOperands else constant_bound(op.upperBoundMap)
        if lower is None or upper is None:
            raise UnsupportedTemplate(
                "affine.for with data-dependent bounds is not modelled; only constant maps are"
            )
        step = op.step.value.data
        trip_count = max(0, -(-(upper - lower) // step))
        if trip_count > self.max_visits:
            # Refusing rather than silently cutting: a hardened loop that is only
            # half-unrolled would be reported as exact, which it would not be.
            raise UnsupportedTemplate(
                f"affine.for runs {trip_count} times, over the --unroll bound of {self.max_visits}"
            )

        carried = [values.get(arg, arg) for arg in op.inits]
        body = op.body.block
        for iteration in range(trip_count):
            induction = self.emit(
                arith.ConstantOp(IntegerAttr(lower + iteration * step, IndexType()))
            ).results[0]
            body_values = dict(values)
            body_values[body.args[0]] = induction
            for arg, value in zip(body.args[1:], carried, strict=True):
                body_values[arg] = value
            carried = list(self.run_block(body, guard, body_values))

        for result, value in zip(op.results, carried, strict=True):
            values[result] = value

    # ---- blocks ---------------------------------------------------------------

    def run_block(
        self, block: Block, guard: SSAValue, values: dict[SSAValue, SSAValue]
    ) -> tuple[SSAValue, ...]:
        """Run a region's block; returns what its `scf.yield` yielded."""
        for op in block.ops:
            if isinstance(op, scf.YieldOp | affine.YieldOp):
                return tuple(values.get(operand, operand) for operand in op.operands)
            self.run_op(op, guard, values)
        return ()

    def run_path(
        self,
        block: Block,
        guard: SSAValue,
        values: dict[SSAValue, SSAValue],
        visits: dict[Block, int],
    ) -> None:
        """Walk a CFG block, following both successors of a branch under their guards."""
        if visits.get(block, 0) >= self.max_visits:
            self.hit_bound = True
            return
        visits = {**visits, block: visits.get(block, 0) + 1}

        for op in block.ops:
            if isinstance(op, cf.BranchOp):
                self.enter(
                    op.successors[0],
                    guard,
                    [values.get(a, a) for a in op.arguments],
                    values,
                    visits,
                )
                return
            if isinstance(op, cf.ConditionalBranchOp):
                condition = values.get(op.cond, op.cond)
                self.observe(guard, condition, CONTROL)
                self.enter(
                    op.then_block,
                    self.conjoin(guard, condition),
                    [values.get(a, a) for a in op.then_arguments],
                    values,
                    visits,
                )
                self.enter(
                    op.else_block,
                    self.conjoin(guard, self.negate(condition)),
                    [values.get(a, a) for a in op.else_arguments],
                    values,
                    visits,
                )
                return
            if isinstance(op, func.ReturnOp):
                # Recorded, not dropped: the leakage property never reads these, but the
                # equivalence gate compares them, and only the walk knows the guard that
                # leads here.
                self.record_result(guard, [values.get(a, a) for a in op.operands])
                return
            if isinstance(op, cf.SwitchOp | cf.AssertOp):
                raise UnsupportedTemplate(f"not modelled yet: {op.name}")
            self.run_op(op, guard, values)

    def enter(
        self,
        block: Block,
        guard: SSAValue,
        arguments: Sequence[SSAValue],
        values: dict[SSAValue, SSAValue],
        visits: dict[Block, int],
    ) -> None:
        successor_values = dict(values)
        for arg, value in zip(block.args, arguments, strict=True):
            successor_values[arg] = value
        self.run_path(block, guard, successor_values, visits)


@dataclass
class FlatProgram:
    block: Block
    bounded: bool
    """True if some path was cut by the unrolling bound: the verdict is bounded too."""


def flatten(
    function: func.FuncOp,
    model: dict[type[Operation], LeakageRule] | None = None,
    max_visits: int = DEFAULT_MAX_VISITS,
) -> FlatProgram:
    """Walk every path of a function body into one guarded straight-line block."""
    flattener = Flattener(DEFAULT_MODEL if model is None else model, max_visits)
    entry = function.body.blocks[0]

    values: dict[SSAValue, SSAValue] = {}
    for arg in entry.args:
        values[arg] = flattener.out.insert_arg(arg.type, len(flattener.out.args))

    flattener.run_path(entry, flattener.constant_true(), values, {})
    return FlatProgram(flattener.out, flattener.hit_bound)
