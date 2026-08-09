"""Step 4 of the plan: the cheap rejection before the solver.

The plan's shape is mark -> sinks -> taint -> CHEAP CHECK -> solver. Until 2026-08-09
only the degenerate cheap check existed (zero sinks of a kind means nothing to prove);
this module supplies the real one: propagate secrecy forward over the *flattened*
program, and if no observation of a kind carries a secret-derived value -- or happens
under a secret-derived guard -- the solver is not consulted for that obligation.

Soundness is one implication, and it must only point this way: taint over-approximates
data flow, so "untainted" means the observed value and its path condition are functions
of shared public inputs alone, hence necessarily equal across the two runs -- `secure`
without asking z3. "Tainted" decides nothing: the solver still rules, so the prefilter
can never flip a verdict, only skip a solver call whose answer is forced.

Two details are load-bearing:

- **The guard counts as part of the sink.** `traces_agree` compares guards as well as
  values, so an observation under a secret-dependent branch can differ between runs
  even when its value is public. A sink is clean only if value AND guard are clean.
- **Memory is one conservative cell.** A store of a tainted value (or at a tainted
  index, or under a tainted guard -- the predicated-store `select` folds the guard into
  the stored value already) taints every later load. Coarse, but the flattened programs
  here are small, and coarseness only costs solver calls, never soundness.
"""

from __future__ import annotations

from collections.abc import Sequence

from xdsl.dialects import memref
from xdsl.ir import Block, SSAValue

from .dialect import OTHER, ObserveOp, ResultOp
from .predication import UnsupportedTemplate


def tainted_kinds(program: Block, secret: Sequence[bool]) -> set[str]:
    """Which observation kinds a secret can reach, over one flattened program.

    `secret` marks the block arguments, in order. Returns the set of kinds whose
    solver query is NOT forced -- every kind absent from it is taint-clean.
    """
    if len(secret) != len(program.args):
        raise UnsupportedTemplate("taint mask does not match the flattened arguments")
    tainted: set[SSAValue] = {
        argument for argument, is_secret in zip(program.args, secret, strict=True) if is_secret
    }
    memory_tainted = False
    hot: set[str] = set()

    for op in program.ops:
        if isinstance(op, ObserveOp):
            kind = op.kind.data if op.kind is not None else OTHER
            if op.guard in tainted or op.value in tainted:
                hot.add(kind)
            continue
        if isinstance(op, ResultOp):
            continue
        if isinstance(op, memref.StoreOp):
            if any(operand in tainted for operand in op.operands):
                memory_tainted = True
            continue
        if isinstance(op, memref.LoadOp):
            if memory_tainted or any(operand in tainted for operand in op.operands):
                tainted.add(op.res)
            continue
        # Everything else -- arith, selects, holes -- computes values from operands:
        # any tainted operand taints every result.
        if any(operand in tainted for operand in op.operands):
            tainted.update(op.results)

    return hot
