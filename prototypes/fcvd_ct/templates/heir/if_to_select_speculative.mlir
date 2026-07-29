// HEIR `--convert-if-to-select` (lib/Transforms/ConvertIfToSelect), applied to the case
// it accepts: both arms are speculatable, so evaluating them unconditionally is safe.
// This is the shape its own test @secret_condition_with_non_secret_int has.
//
// Expected: CT-PRESERVING -- the branch observation disappears and nothing replaces it.
builtin.module {
  func.func @source(%cond: i1, %x: i16) {
    %r = scf.if %cond -> (i16) {
      %a = arith.addi %x, %x : i16
      scf.yield %a : i16
    } else {
      scf.yield %x : i16
    }
    func.return
  }

  func.func @target(%cond: i1, %x: i16) {
    %a = arith.addi %x, %x : i16
    %r = arith.select %cond, %a, %x : i16
    func.return
  }
}
