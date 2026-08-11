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
        ("mem2reg_if", "ct-preserving"),
        ("mem2reg_if_stale", "ct-preserving"),
        ("lower_affine_for_load_store", "ct-preserving"),
        ("lower_affine_wrong_index", "ct-preserving"),
        ("affine_cfg_raise_store", "ct-preserving"),
        ("affine_cfg_wrong_map", "ct-preserving"),
        ("polygeist_to_llvm_arith", "ct-preserving"),
        ("polygeist_to_llvm_swapped_sub", "ct-preserving"),
        ("polygeist_to_llvm_memref", "ct-preserving"),
        ("polygeist_to_llvm_memref_offset", "ct-preserving"),
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


def test_mem2reg_both_halves():
    """--polygeist-mem2reg: the faithful forwarding is VERIFIED (values-only equivalence,
    declared in the template); the stale forwarding adds no observation, so only the
    equivalence half can refuse it -- and does (measured 2026-08-09)."""
    from fcvdct.structural import check_template

    ctx = make_context()
    path = ROOT / "templates" / "polygeist" / "mem2reg_if.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "verified", (gate.constant_time.reason, gate.equivalence.reason)
    assert not gate.equivalence.memory_compared, "the declared values-only mode must be visible"

    path = ROOT / "templates" / "polygeist" / "mem2reg_if_stale.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "rejected"
    assert gate.constant_time.verdict == "ct-preserving"
    assert gate.equivalence.verdict == "not-equivalent"


def test_lower_affine_both_halves():
    """--lower-affine: the faithful lowering is VERIFIED; the off-by-one final index is
    refused by the equivalence half and only that half -- a shifted constant address is
    still deterministic, so the trace cannot tell (measured 2026-08-09)."""
    from fcvdct.structural import check_template

    ctx = make_context()
    path = ROOT / "templates" / "polygeist" / "lower_affine_for_load_store.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "verified", (gate.constant_time.reason, gate.equivalence.reason)

    path = ROOT / "templates" / "polygeist" / "lower_affine_wrong_index.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "rejected"
    assert gate.constant_time.verdict == "ct-preserving"
    assert gate.equivalence.verdict == "not-equivalent"


def test_memory_reading_identity_is_preserving():
    """The 2026-08-09 encoding fix, pinned: a template whose two sides are the SAME
    memory-reading loop must verify. Before the fix each of the four programs got a
    fresh initial memory, so the identity itself came back ct-breaking."""
    from fcvdct.structural import check_template

    template = """
builtin.module {
  func.func @source(%m: memref<4xi8>) -> i8 {
    %c0 = arith.constant 0 : index
    %c3 = arith.constant 3 : index
    %c1 = arith.constant 1 : index
    scf.for %i = %c0 to %c3 step %c1 {
      %old = memref.load %m[%i] : memref<4xi8>
      %new = "fcvd.hole"(%old) {sym_name = "BODY", leaks = 1 : i64} : (i8) -> i8
    }
    %out = memref.load %m[%c1] : memref<4xi8>
    func.return %out : i8
  }
  func.func @target(%m: memref<4xi8>) -> i8 {
    %c0 = arith.constant 0 : index
    %c3 = arith.constant 3 : index
    %c1 = arith.constant 1 : index
    scf.for %i = %c0 to %c3 step %c1 {
      %old = memref.load %m[%i] : memref<4xi8>
      %new = "fcvd.hole"(%old) {sym_name = "BODY", leaks = 1 : i64} : (i8) -> i8
    }
    %out = memref.load %m[%c1] : memref<4xi8>
    func.return %out : i8
  }
}
"""
    ctx = make_context()
    gate = check_template(ctx, Parser(ctx, template).parse_module())
    assert gate.verdict == "verified", (gate.constant_time.reason, gate.equivalence.reason)


def test_affine_cfg_both_halves():
    """--affine-cfg: the composed-map raise is VERIFIED; the wrong-stride twin is
    refused by the equivalence half alone, through the memory clause -- nothing is
    returned, so the memory left behind is the entire claim (measured 2026-08-09)."""
    from fcvdct.structural import check_template

    ctx = make_context()
    path = ROOT / "templates" / "polygeist" / "affine_cfg_raise_store.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "verified", (gate.constant_time.reason, gate.equivalence.reason)

    path = ROOT / "templates" / "polygeist" / "affine_cfg_wrong_map.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "rejected"
    assert gate.constant_time.verdict == "ct-preserving"
    assert gate.equivalence.verdict == "not-equivalent"


def test_polygeist_to_llvm_both_halves():
    """--convert-polygeist-to-llvm, integer-arithmetic slice: 1:1 arith->llvm mapping
    is VERIFIED; the swapped subtraction is refused by the equivalence half alone --
    pure arithmetic emits no observation, so the leakage half is vacuous on both
    (measured 2026-08-09)."""
    from fcvdct.structural import check_template

    ctx = make_context()
    path = ROOT / "templates" / "polygeist" / "polygeist_to_llvm_arith.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "verified", (gate.constant_time.reason, gate.equivalence.reason)
    assert gate.constant_time.n_source_observations == 0, "the leakage half must be vacuous here"

    path = ROOT / "templates" / "polygeist" / "polygeist_to_llvm_swapped_sub.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "rejected"
    assert gate.equivalence.verdict == "not-equivalent"


def test_polygeist_to_llvm_memref_both_halves():
    """--convert-polygeist-to-llvm, memory slice: memref.load/store -> gep+llvm.load/store
    is VERIFIED (same cell, same byte); the off-by-one GEP is refused by the equivalence
    half alone -- a deterministic wrong address the trace cannot see (measured 2026-08-09)."""
    from fcvdct.structural import check_template

    ctx = make_context()
    path = ROOT / "templates" / "polygeist" / "polygeist_to_llvm_memref.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "verified", (gate.constant_time.reason, gate.equivalence.reason)
    assert gate.constant_time.n_target_observations >= 1, (
        "the llvm.getelementptr address must be observed, or the channel is invisible"
    )

    path = ROOT / "templates" / "polygeist" / "polygeist_to_llvm_memref_offset.mlir"
    gate = check_template(ctx, Parser(ctx, path.read_text(), str(path)).parse_module())
    assert gate.verdict == "rejected"
    assert gate.equivalence.verdict == "not-equivalent"


def test_llvm_gep_leaks_a_secret_index():
    """The GEP leakage rule is load-bearing: a secret index through getelementptr+load
    is INSECURE on the address obligation. Without the rule this would read secure and
    the memref->llvm address channel would be invisible."""
    from fcvdct.selfcomp import check_module

    kernel = """
builtin.module {
  func.func @k(%p: !llvm.ptr, %s: i64 {fcvdct.secret}) -> i8 {
    %a = "llvm.getelementptr"(%p, %s) <{rawConstantIndices = array<i32: -1>, elem_type = i8}> : (!llvm.ptr, i64) -> !llvm.ptr
    %v = "llvm.load"(%a) <{ordering = 0 : i64}> : (!llvm.ptr) -> i8
    func.return %v : i8
  }
}
"""
    ctx = make_context()
    result = check_module(ctx, Parser(ctx, kernel).parse_module())
    assert result.verdict == "insecure"
    address = next(o for o in result.obligations if o.kind == "address")
    assert address.verdict == "insecure"
