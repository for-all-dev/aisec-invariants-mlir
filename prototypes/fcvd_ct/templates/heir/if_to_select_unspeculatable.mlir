// The same lowering applied to the case HEIR's pass *refuses*: an arm containing
// `arith.divui`, taken from its own negative test (tests/Transforms/convert_if_to_select/
// invalid_conditionals.mlir, @non_speculative_code), where the pass emits "Cannot
// convert scf.if to arith.select, as it contains code that cannot be safely hoisted".
//
// The refusal is usually justified by undefined behaviour -- speculating a division by
// zero. This says something else and independent: even where the division is defined,
// hoisting it out of the branch makes it run on every input, so a divisor that only
// reached the divider on one path now always reaches it. The side condition the pass
// enforces is necessary for constant-time too, not only for UB.
//
// Expected: CT-BREAKING. The pass is right to refuse; this is the proof that it must.
builtin.module {
  func.func @source(%cond: i1, %x: i16, %divisor: i16) {
    %r = scf.if %cond -> (i16) {
      %q = arith.divui %x, %divisor : i16
      scf.yield %q : i16
    } else {
      scf.yield %x : i16
    }
    func.return
  }

  func.func @target(%cond: i1, %x: i16, %divisor: i16) {
    %q = arith.divui %x, %divisor : i16
    %r = arith.select %cond, %q, %x : i16
    func.return
  }
}
