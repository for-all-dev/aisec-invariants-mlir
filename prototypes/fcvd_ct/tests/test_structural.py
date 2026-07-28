"""Verdicts for the structural lowering templates, plus the mutations that show the
encoding is load-bearing rather than accidentally green."""

from __future__ import annotations

from pathlib import Path

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.parser import Parser
from xdsl_smt.dialects import smt_dialect as smt

from fcvdct import structural
from fcvdct.context import make_context
from fcvdct.structural import check_lowering

TEMPLATES = Path(__file__).parent.parent / "templates"

# template -> (verdict, source observations, target observations)
EXPECTED = {
    "scf_if_to_cf": ("ct-preserving", 3, 3),
    "if_to_select_pure": ("ct-preserving", 1, 0),
    "select_to_cf": ("ct-breaking", 0, 1),
    "if_to_select_leaky": ("ct-breaking", 3, 2),
    "swapped_arms": ("ct-breaking", 3, 3),
    "loop_unsupported": ("unknown", 0, 0),
}


def load(name: str) -> tuple[Context, ModuleOp]:
    ctx = make_context()
    text = (TEMPLATES / f"{name}.mlir").read_text()
    return ctx, Parser(ctx, text, name).parse_module()


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_verdict(name: str):
    verdict, n_source, n_target = EXPECTED[name]
    ctx, module = load(name)
    result = check_lowering(ctx, module)
    assert result.verdict == verdict, result.reason or result.solver_output
    assert result.n_source_observations == n_source
    assert result.n_target_observations == n_target


def test_loops_are_refused_by_name():
    ctx, module = load("loop_unsupported")
    assert "loops are not modelled" in check_lowering(ctx, module).reason


def test_guards_are_load_bearing(monkeypatch: pytest.MonkeyPatch):
    """Comparing observations without their guards hides a real leak.

    Under if-conversion both arms are evaluated, so an unguarded trace credits the
    source with the untaken arm's observations too — which is exactly the antecedent of
    the property, and makes `if_to_select_leaky` come back preserving. Guards are what
    keep that from happening, and this test fails if they stop being applied.
    """

    def unguarded(builder, left, right):  # type: ignore[no-untyped-def]
        terms = [
            builder.insert(
                smt.EqOp(
                    structural._observed_value(builder, one.value),
                    structural._observed_value(builder, other.value),
                )
            ).res
            for one, other in zip(left.observations, right.observations, strict=True)
        ]
        return structural._conjoin(builder, terms)

    ctx, module = load("if_to_select_leaky")
    assert check_lowering(ctx, module).verdict == "ct-breaking"

    monkeypatch.setattr(structural, "_traces_agree", unguarded)
    ctx, module = load("if_to_select_leaky")
    assert check_lowering(ctx, module).verdict == "ct-preserving"


def test_hole_congruence_is_load_bearing(monkeypatch: pytest.MonkeyPatch):
    """Without the congruence axioms a *correct* lowering stops being provable.

    The target's holes become symbols unrelated to the source's, so `scf_if_to_cf`
    turns into a false alarm rather than into a false pass.
    """
    monkeypatch.setattr(structural, "_hole_congruence", lambda builder, traces: [])
    ctx, module = load("scf_if_to_cf")
    assert check_lowering(ctx, module).verdict == "ct-breaking"
