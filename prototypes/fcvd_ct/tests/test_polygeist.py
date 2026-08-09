"""Polygeist: the loop's own regression net.

Each template pins the verdict the tool printed when it was written. The pair here is
deliberately kept even though the second one did not do what it was written to do --
see its header, and the journal entry for 2026-07-29.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from xdsl.parser import Parser

from fcvdct.context import make_context
from fcvdct.structural import check_lowering

ROOT = Path(__file__).parent.parent


@pytest.mark.parametrize(
    ("template", "verdict"),
    [
        ("canonicalize_for_propagate", "ct-preserving"),
        ("canonicalize_for_propagate_moved", "ct-preserving"),
        ("loop_restructure_while", "ct-preserving"),
        ("loop_restructure_dowhile", "ct-breaking"),
    ],
)
def test_templates(template: str, verdict: str):
    ctx = make_context()
    path = ROOT / "templates" / "polygeist" / f"{template}.mlir"
    result = check_lowering(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert result.verdict == verdict, result.reason


def test_hole_congruence_ignores_poison_not_values():
    """The fix this iteration found: congruence compares values, not definedness.

    A loop whose bound is a function argument makes the unrolled `select` inherit that
    argument's poison marker, so comparing raw pairs made congruence fail and reported a
    correct rewrite as ct-breaking. Comparing values is what `traces_agree` already did
    for observations. The same template with constant bounds always passed; this one
    only passes with the fix in place.
    """
    ctx = make_context()
    path = ROOT / "templates" / "polygeist" / "canonicalize_for_propagate.mlir"
    result = check_lowering(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert result.verdict == "ct-preserving"
    assert result.bounded, "the loop is unrolled, so the verdict must announce itself as bounded"


def test_loop_restructure_both_halves():
    """--loop-restructure: the while form is VERIFIED (both halves), the do-while twin
    is rejected by the leakage half alone -- its returned flag is constant false on
    both sides, so equivalence rightly holds (measured 2026-08-09)."""
    from fcvdct.structural import check_template

    ctx = make_context()
    path = ROOT / "templates" / "polygeist" / "loop_restructure_while.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "verified", (gate.constant_time.reason, gate.equivalence.reason)

    path = ROOT / "templates" / "polygeist" / "loop_restructure_dowhile.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "rejected"
    assert gate.constant_time.verdict == "ct-breaking"
    assert gate.equivalence.verdict == "equivalent"
