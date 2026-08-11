// The falsifying twin of loop_restructure_while.mlir: the same cf loop, restructured
// wrongly into do-while form — the body sits in the before-region AHEAD of the check,
// so it runs once before the loop guard is ever consulted. This is the textbook
// restructuring hazard: the body of a guarded loop must not execute before its first
// check. (LoopRestructure.cpp does not do this; the twin exists to show the checker
// would catch it if it did.)
//
// Expected: CT-BREAKING — on a zero-trip loop (%ub < 0) the source never observes the
// body, the target observes it once, unguarded, so two runs that agree on every source
// observation can still differ on the target's. Equivalence is expected to fail too
// (the exit values leave after one extra increment); both verdicts are the tool's to
// print, not this header's to assert.
//
// Measured 2026-08-09: CT-BREAKING as predicted; equivalence came back EQUIVALENT,
// and rightly so — the returned flag is `slt(i, 0)` over a non-negative counter, so it
// is constant false on both sides. The bug is in the trace, not in the value, which is
// exactly why the leakage half exists.
builtin.module {
  func.func @source(%ub: i64, %x: i32) -> i1 {
    %c0 = arith.constant 0 : i64
    %c1 = arith.constant 1 : i64
    cf.br ^bb1(%c0 : i64)
  ^bb1(%i: i64):
    %flag = arith.cmpi slt, %i, %c0 : i64
    %go = arith.cmpi sle, %i, %ub : i64
    cf.cond_br %go, ^bb2, ^bb3
  ^bb2:
    %seen = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 1 : i64} : (i32) -> i32
    %next = arith.addi %i, %c1 : i64
    cf.br ^bb1(%next : i64)
  ^bb3:
    func.return %flag : i1
  }

  func.func @target(%ub: i64, %x: i32) -> i1 {
    %c0 = arith.constant 0 : i64
    %c1 = arith.constant 1 : i64
    %dead = arith.constant false
    %res:2 = scf.while (%i = %c0, %carried = %dead) : (i64, i1) -> (i64, i1) {
      %seen = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 1 : i64} : (i32) -> i32
      %next = arith.addi %i, %c1 : i64
      %flag = arith.cmpi slt, %next, %c0 : i64
      %go = arith.cmpi sle, %next, %ub : i64
      scf.condition(%go) %next, %flag : i64, i1
    } do {
    ^bb0(%i2: i64, %carried2: i1):
      scf.yield %i2, %carried2 : i64, i1
    }
    func.return %res#1 : i1
  }
}
