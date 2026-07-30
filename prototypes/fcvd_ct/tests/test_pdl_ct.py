"""End-to-end verdicts for the pattern corpus.

Each case pins the verdict *and* the number of observations on each side, so a change
that silently stops recording leakage fails here rather than turning every rewrite
green.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.dialects.pdl import PatternOp
from xdsl.parser import Parser

from fcvdct.context import make_context
from fcvdct.pdl_ct import check_pattern

PATTERNS = Path(__file__).parent.parent / "patterns"

# pattern file -> (verdict, source observations, target observations)
EXPECTED = {
    "mul_to_shl": ("ct-preserving", 0, 0),
    "div_to_shift": ("ct-preserving", 2, 0),
    "rem_idempotent": ("ct-preserving", 4, 2),
    "shift_to_div": ("ct-breaking", 0, 2),
    "mask_to_rem": ("ct-breaking", 0, 2),
    "div_swap_operand": ("ct-breaking", 2, 2),
    "unsupported_float": ("unknown", 0, 0),
}


def load(name: str) -> tuple[Context, ModuleOp]:
    ctx = make_context()
    text = (PATTERNS / f"{name}.mlir").read_text()
    module = Parser(ctx, text, name).parse_module()
    patterns = [op for op in module.walk() if isinstance(op, PatternOp)]
    assert len(patterns) == 1
    return ctx, ModuleOp([patterns[0].clone()])


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_verdict(name: str):
    verdict, n_source, n_target = EXPECTED[name]
    ctx, module = load(name)
    result = check_pattern(ctx, module)
    assert result.verdict == verdict, result.reason or result.solver_output
    assert result.n_source_observations == n_source
    assert result.n_target_observations == n_target


def test_query_is_not_vacuous():
    """The proved queries must actually reach the solver with an obligation in them."""
    ctx, module = load("div_to_shift")
    result = check_pattern(ctx, module)
    assert "(check-sat)" in result.smtlib
    assert result.smtlib.count("(assert") >= 2  # match assumptions + our obligation
    assert result.solver_output.startswith("unsat")


def test_counterexample_is_reported():
    ctx, module = load("div_swap_operand")
    result = check_pattern(ctx, module)
    assert result.verdict == "ct-breaking"
    assert "define-fun" in result.counterexample
