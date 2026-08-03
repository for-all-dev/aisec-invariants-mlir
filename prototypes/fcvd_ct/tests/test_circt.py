"""CIRCT: the arithmetic path of the software-to-hardware pipeline.

Two steps of CIRCT's own pipeline are checked here, both transcribed from the C++ that
implements them, and they go in opposite directions: `--map-arith-to-comb` closes the
division channel by turning a variable-latency instruction into a fixed-delay circuit,
and `--convert-comb-to-arith`, which arcilator reaches when it simulates that circuit on
the host, opens it again.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from xdsl.dialects import comb
from xdsl.parser import Parser
from xdsl_smt.passes.lower_to_smt.smt_lowerer import SMTLowerer

from fcvdct.context import make_context
from fcvdct.hw_ops import HWConstantOp
from fcvdct.leakage import DEFAULT_MODEL
from fcvdct.selfcomp import check_module
from fcvdct.structural import check_lowering

ROOT = Path(__file__).parent.parent


@pytest.mark.parametrize(
    ("template", "verdict", "observations"),
    [
        ("map_arith_to_comb_pure", "ct-preserving", (0, 0)),
        ("map_arith_to_comb_div", "ct-preserving", (4, 0)),
        ("map_arith_to_comb_minmax", "ct-preserving", (0, 0)),
        ("comb_to_arith_div", "ct-breaking", (0, 2)),
    ],
)
def test_templates(template: str, verdict: str, observations: tuple[int, int]):
    ctx = make_context()
    path = ROOT / "templates" / "circt" / f"{template}.mlir"
    result = check_lowering(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert result.verdict == verdict, result.reason
    assert (result.n_source_observations, result.n_target_observations) == observations


def test_simulating_the_divider_is_what_introduces_the_leak():
    """The same circuit and the same secret, before and after the step."""
    ctx = make_context()
    kernels = ROOT / "kernels" / "circt"
    hardware = (kernels / "hw_divide.mlir").read_text()
    simulated = (kernels / "hw_divide_simulated.mlir").read_text()

    assert check_module(ctx, Parser(ctx, hardware, "hw").parse_module()).verdict == "secure"
    result = check_module(ctx, Parser(ctx, simulated, "sim").parse_module())
    assert result.verdict == "insecure"
    assert {o.kind for o in result.obligations if o.verdict == "insecure"} == {"latency"}


def test_comb_arithmetic_is_deliberately_not_observed():
    """The hardware model is a choice, and this is where it is made.

    `comb.divu` is a combinational divider: the same operands take the same time, so it
    emits no observation, while `arith.divui` does. Every CIRCT verdict here rests on
    that difference, so it is pinned rather than left to be noticed.
    """
    for op in (comb.DivUOp, comb.DivSOp, comb.ModUOp, comb.ModSOp, comb.MuxOp):
        assert op not in DEFAULT_MODEL


def test_hw_constant_has_syntax_and_semantics():
    """Ours, not upstream's: xdsl-smt declares the operation and stops there."""
    ctx = make_context()
    module = Parser(
        ctx,
        "func.func @f() -> i32 {\n  %k = hw.constant 7 : i32\n  func.return %k : i32\n}\n",
        "hw",
    ).parse_module()
    assert "hw.constant 7" in str(module)
    assert HWConstantOp in SMTLowerer.op_semantics
