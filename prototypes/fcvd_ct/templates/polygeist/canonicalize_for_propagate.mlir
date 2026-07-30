// Polygeist `--canonicalize-for`, the `PropagateInLoopBody` pattern, transcribed from
// lib/polygeist/Passes/CanonicalizeFor.cpp:26-51 (pass registered at
// tools/cgeist/driver.cc:685, name from include/polygeist/Passes/Passes.td).
//
// The rule: for each (init, region argument, yielded value) triple of an `scf.for`, if
// the init has a defining operation with one result AND the loop yields that same value
// back unchanged, the uses of the region argument are replaced by the init directly.
//
//     if (op && (op->getNumResults() == 1) && (iterOperand == yieldOperand))
//       regionArg.replaceAllUsesWith(op->getResult(0));
//
// So it only fires on an iteration argument the body never modifies. Nothing about the
// trip count, the branches or the memory touched changes — only which SSA value the
// body reads, and the side condition says the two are equal at every iteration.
//
// The body is a hole with one observation, so that a change in the value it receives
// would show up as a different trace rather than being invisible.
//
// Expected: CT-PRESERVING, same observation count on both sides. Bounded, because the
// loop is unrolled. The falsifying twin is canonicalize_for_propagate_moved.mlir.
builtin.module {
  func.func @source(%lb: index, %ub: index, %step: index, %x: i32) {
    %init = arith.addi %x, %x : i32
    %r = scf.for %i = %lb to %ub step %step iter_args(%carried = %init) -> (i32) {
      %seen = "fcvd.hole"(%carried) {sym_name = "body", leaks = 1 : i64} : (i32) -> i32
      scf.yield %carried : i32
    }
    func.return
  }

  func.func @target(%lb: index, %ub: index, %step: index, %x: i32) {
    %init = arith.addi %x, %x : i32
    %r = scf.for %i = %lb to %ub step %step iter_args(%carried = %init) -> (i32) {
      %seen = "fcvd.hole"(%init) {sym_name = "body", leaks = 1 : i64} : (i32) -> i32
      scf.yield %carried : i32
    }
    func.return
  }
}
