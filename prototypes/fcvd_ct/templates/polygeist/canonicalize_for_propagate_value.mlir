// Polygeist `--canonicalize-for`, `PropagateInLoopBody`, transcribed from
// lib/polygeist/Passes/CanonicalizeFor.cpp:26-51 (pass at tools/cgeist/driver.cc:685) --
// the same rule as canonicalize_for_propagate.mlir, written so that the *value* half of
// the gate has something to compare.
//
// The difference from that file is only in the plumbing: the body's computed result is
// accumulated into a second iteration argument and returned, so what the body was handed
// reaches the function's result. The rewrite itself is unchanged -- the body reads
// `%carried` in @source and `%init` in @target, and the pattern's side condition
// (`iterOperand == yieldOperand`, so the loop yields the argument back unchanged) holds
// here.
//
// Expected: VERIFIED. Constant-time preserving, as for the void version, *and*
// equivalent: `%carried` is `%init` at every iteration, so hole congruence gives the two
// bodies equal results and the accumulated sums agree. Bounded, because the loop is
// unrolled. The falsifying twin is canonicalize_for_propagate_moved_value.mlir.
builtin.module {
  func.func @source(%lb: index, %ub: index, %step: index, %x: i32) -> i32 {
    %zero = arith.constant 0 : i32
    %init = arith.addi %x, %x : i32
    %carried_out, %acc_out = scf.for %i = %lb to %ub step %step
        iter_args(%carried = %init, %acc = %zero) -> (i32, i32) {
      %v, %l = "fcvd.hole"(%carried) {sym_name = "body", leaks = 1 : i64} : (i32) -> (i32, i32)
      %sum = arith.addi %acc, %v : i32
      scf.yield %carried, %sum : i32, i32
    }
    func.return %acc_out : i32
  }

  func.func @target(%lb: index, %ub: index, %step: index, %x: i32) -> i32 {
    %zero = arith.constant 0 : i32
    %init = arith.addi %x, %x : i32
    %carried_out, %acc_out = scf.for %i = %lb to %ub step %step
        iter_args(%carried = %init, %acc = %zero) -> (i32, i32) {
      %v, %l = "fcvd.hole"(%init) {sym_name = "body", leaks = 1 : i64} : (i32) -> (i32, i32)
      %sum = arith.addi %acc, %v : i32
      scf.yield %carried, %sum : i32, i32
    }
    func.return %acc_out : i32
  }
}
