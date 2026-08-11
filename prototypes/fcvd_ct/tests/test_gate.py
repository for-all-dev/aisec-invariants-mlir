"""The gate: a lowering is verified only if it preserves constant-time *and* meaning.

The four mutation tests at the bottom are the point of this file. Each switches off one
piece of the equivalence encoding and shows what breaks -- three of them turn a correct
lowering into a false alarm, and the first turns a *wrong* one into a pass, which is the
failure mode that matters.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.parser import Parser

from fcvdct import structural
from fcvdct.context import make_context
from fcvdct.structural import check_equivalence, check_template

TEMPLATES = Path(__file__).parent.parent / "templates"

# template -> (gate, constant-time, equivalence, values compared)
EXPECTED = {
    # The pair the gate exists for. Both halves agree on the correct rewrite; on the
    # mutation the leakage half still passes and only the value half refutes it.
    "polygeist/canonicalize_for_propagate_value": ("verified", "ct-preserving", "equivalent", 1),
    "polygeist/canonicalize_for_propagate_moved_value": (
        "rejected",
        "ct-preserving",
        "not-equivalent",
        1,
    ),
    # A correct lowering and a leaking one, neither of which changes what is computed:
    # the two halves are independent, and the second shows the gate rejects on either.
    "scf_if_to_cf": ("verified", "ct-preserving", "equivalent", 0),
    "select_to_cf": ("rejected", "ct-breaking", "equivalent", 0),
    # Unrolled loops: bounded on both halves, and the skeleton computes what the loop did.
    "scf_for_to_cf": ("verified", "ct-preserving", "equivalent", 0),
    # No semantics for `cf.switch`, so neither half has an answer. Never a pass.
    "switch_unsupported": ("unknown", "unknown", "unknown", 0),
}


def load(name: str) -> tuple[Context, ModuleOp]:
    ctx = make_context()
    text = (TEMPLATES / f"{name}.mlir").read_text()
    return ctx, Parser(ctx, text, name).parse_module()


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_gate_verdict(name: str):
    gate, ct, equivalence, n_compared = EXPECTED[name]
    ctx, module = load(name)
    result = check_template(ctx, module)
    assert result.constant_time.verdict == ct, result.reason
    assert result.equivalence.verdict == equivalence, result.reason
    assert result.verdict == gate, result.reason
    assert result.equivalence.n_compared == n_compared


def test_unrolled_equivalence_says_it_is_bounded():
    """A loop verdict that only covers the unrolled iterations must announce it."""
    ctx, module = load("scf_for_to_cf")
    assert check_equivalence(ctx, module).bounded
    ctx, module = load("scf_if_to_cf")
    assert not check_equivalence(ctx, module).bounded


def test_a_template_returning_nothing_says_so():
    """`equivalent` with no values compared is a weaker statement, and prints as one."""
    ctx, module = load("scf_if_to_cf")
    result = check_equivalence(ctx, module)
    assert result.verdict == "equivalent"
    assert result.n_compared == 0


def test_returned_values_are_load_bearing(monkeypatch: pytest.MonkeyPatch):
    """Without the value comparison the stale-value rewrite passes.

    This is the gap the gate closes, made falsifiable: drop the returned values from the
    query and the mutation Polygeist refuses to perform comes back `equivalent`, which is
    exactly what the leakage property alone reports.
    """
    name = "polygeist/canonicalize_for_propagate_moved_value"
    ctx, module = load(name)
    assert check_equivalence(ctx, module).verdict == "not-equivalent"

    def no_results(builder, before, after):  # type: ignore[no-untyped-def]
        return builder.insert(structural.smt.ConstantBoolOp(True)).result

    monkeypatch.setattr(structural, "_value_refinement", no_results)
    ctx, module = load(name)
    assert check_equivalence(ctx, module).verdict == "equivalent"


def test_exact_hole_congruence_is_load_bearing(monkeypatch: pytest.MonkeyPatch):
    """Relating hole outputs by value only refutes a *correct* rewrite.

    The leakage query compares values and ignores definedness on purpose. Carried into
    the equivalence query that becomes a false alarm: the accumulated result inherits a
    free poison marker in one program and not in the other.
    """
    name = "polygeist/canonicalize_for_propagate_value"
    ctx, module = load(name)
    assert check_equivalence(ctx, module).verdict == "equivalent"

    congruence = structural._hole_congruence
    monkeypatch.setattr(
        structural,
        "_hole_congruence",
        lambda builder, traces, exact=False: congruence(builder, traces, exact=False),
    )
    ctx, module = load(name)
    assert check_equivalence(ctx, module).verdict == "not-equivalent"


def test_defined_inputs_are_load_bearing():
    """Without "the arguments are defined", a guarded divisor looks like a value change.

    CIRCT's `--convert-comb-to-arith` inserts `divisor = (b == 0) ? 1 : b` precisely so
    the division is defined. If the argument may be poison the guard inherits it, the
    target raises UB the source did not, and a correct pattern is refuted. This is the P0
    finding of the plan note arriving through the UB clause.
    """
    ctx, module = load("circt/comb_to_arith_div")
    assert check_equivalence(ctx, module).verdict == "equivalent"

    ctx, module = load("circt/comb_to_arith_div")
    assert check_equivalence(ctx, module, assume_defined_inputs=False).verdict == "not-equivalent"


def test_hole_congruence_still_ignores_poison_for_leakage():
    """The leakage query keeps the weak axiom: this is not a change to that verdict.

    Fixed in `6b4cf86` after unrolling a loop with a symbolic bound reported a correct
    rewrite as breaking. The equivalence query needs the strong form; the leakage query
    must not get it.
    """
    ctx, module = load("polygeist/canonicalize_for_propagate_value")
    assert structural.check_lowering(ctx, module).verdict == "ct-preserving"
