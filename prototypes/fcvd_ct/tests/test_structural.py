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
    # loops, unrolled: the correct skeleton, and the early exit that breaks it
    "scf_for_bounded": ("ct-preserving", 9, 9),
    "scf_for_to_cf": ("ct-preserving", 9, 8),
    "loop_early_exit": ("ct-breaking", 9, 12),
    "while_unsupported": ("unknown", 0, 0),
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


def test_unmodelled_loops_are_refused_by_name():
    ctx, module = load("while_unsupported")
    assert "not modelled yet: scf.while" in check_lowering(ctx, module).reason


def test_unrolled_verdicts_say_they_are_bounded():
    """A verdict that only covers the unrolled iterations must announce it."""
    ctx, module = load("scf_for_to_cf")
    assert check_lowering(ctx, module).bounded
    ctx, module = load("scf_if_to_cf")
    assert not check_lowering(ctx, module).bounded


def test_unrolling_bound_changes_the_trace_length():
    ctx, module = load("scf_for_to_cf")
    short = check_lowering(ctx, module, max_visits=2)
    assert short.verdict == "ct-preserving"
    assert short.n_source_observations < EXPECTED["scf_for_to_cf"][1]


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
