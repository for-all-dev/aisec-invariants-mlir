// The falsifying twin of canonicalize_for_propagate_value.mlir, and the reason the gate
// exists: the same replacement applied where Polygeist refuses to apply it -- the loop
// *does* modify the iteration argument, so `iterOperand == yieldOperand` is false
// (lib/polygeist/Passes/CanonicalizeFor.cpp:45) and the body would be reading a stale
// value. Polygeist does not perform this rewrite.
//
// canonicalize_for_propagate_moved.mlir is the same mutation with nothing returned, and
// it comes back CT-PRESERVING. That is the correct answer for the leakage property and
// the whole problem: reading a stale value adds no observation, so a property about
// observations cannot see it. The journal entry of 2026-07-29T12:40Z recorded that as a
// limit of the instrument.
//
// Here the body's result reaches the function's result, so the value half has something
// to compare. `%carried` runs init, init+1, init+2, ... while @target hands the body
// `%init` every time; congruence relates only the instances whose inputs agree, so the
// accumulated sums may differ, and z3 shows an input where they do.
//
// Expected: REJECTED, and specifically the split that matters -- CT-PRESERVING (the
// leakage property still passes it) together with NOT-EQUIVALENT (the value property
// refutes it). Bounded, because the loop is unrolled.
builtin.module {
  func.func @source(%lb: index, %ub: index, %step: index, %x: i32) -> i32 {
    %zero = arith.constant 0 : i32
    %one = arith.constant 1 : i32
    %init = arith.addi %x, %x : i32
    %carried_out, %acc_out = scf.for %i = %lb to %ub step %step
        iter_args(%carried = %init, %acc = %zero) -> (i32, i32) {
      %v, %l = "fcvd.hole"(%carried) {sym_name = "body", leaks = 1 : i64} : (i32) -> (i32, i32)
      %sum = arith.addi %acc, %v : i32
      %next = arith.addi %carried, %one : i32
      scf.yield %next, %sum : i32, i32
    }
    func.return %acc_out : i32
  }

  func.func @target(%lb: index, %ub: index, %step: index, %x: i32) -> i32 {
    %zero = arith.constant 0 : i32
    %one = arith.constant 1 : i32
    %init = arith.addi %x, %x : i32
    %carried_out, %acc_out = scf.for %i = %lb to %ub step %step
        iter_args(%carried = %init, %acc = %zero) -> (i32, i32) {
      %v, %l = "fcvd.hole"(%init) {sym_name = "body", leaks = 1 : i64} : (i32) -> (i32, i32)
      %sum = arith.addi %acc, %v : i32
      %next = arith.addi %carried, %one : i32
      scf.yield %next, %sum : i32, i32
    }
    func.return %acc_out : i32
  }
}
