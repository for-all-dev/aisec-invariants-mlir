// The intended control for canonicalize_for_propagate.mlir -- the same replacement
// applied where the pattern refuses to apply it, i.e. where the loop *does* modify the
// iteration argument, so `iterOperand == yieldOperand` is false
// (lib/polygeist/Passes/CanonicalizeFor.cpp:45). Polygeist does not perform this
// rewrite.
//
// It was expected to come back CT-BREAKING. It does not: **CT-PRESERVING**, and that is
// the correct answer, which makes this file a result about the instrument rather than
// about Polygeist.
//
// Reading a stale value is a *value* bug, not an added leak. The property proved here is
// `L_source(x) = L_source(x') => L_target(x) = L_target(x')` -- the rewrite may remove
// leakage, never add it. The target calls the body with `%init` only, and `%init` is
// exactly what the source passes on its first iteration, so hole congruence ties the
// target's observations to observations the source already makes. The target leaks a
// subset. Nothing is added, so nothing is reported.
//
// The consequence, recorded in docs/research/polygeist-verification.agents.md: the side
// condition this pass enforces is about functional equivalence, and the leakage property
// is blind to it by construction. Checking it needs the value-refinement criterion --
// upstream FCVD's, which `fcvd-ct-pdl` deliberately switches off -- not this one.
builtin.module {
  func.func @source(%lb: index, %ub: index, %step: index, %x: i32) {
    %one = arith.constant 1 : i32
    %init = arith.addi %x, %x : i32
    %r = scf.for %i = %lb to %ub step %step iter_args(%carried = %init) -> (i32) {
      %seen = "fcvd.hole"(%carried) {sym_name = "body", leaks = 1 : i64} : (i32) -> i32
      %next = arith.addi %carried, %one : i32
      scf.yield %next : i32
    }
    func.return
  }

  func.func @target(%lb: index, %ub: index, %step: index, %x: i32) {
    %one = arith.constant 1 : i32
    %init = arith.addi %x, %x : i32
    %r = scf.for %i = %lb to %ub step %step iter_args(%carried = %init) -> (i32) {
      %seen = "fcvd.hole"(%init) {sym_name = "body", leaks = 1 : i64} : (i32) -> i32
      %next = arith.addi %carried, %one : i32
      scf.yield %next : i32
    }
    func.return
  }
}
