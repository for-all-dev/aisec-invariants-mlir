// HEIR `--mod-arith-to-arith`, the conditional-subtraction operation `mod_arith.subifge`
// -- "compute (x >= y) ? x - y : x", the reduction step of Barrett/Montgomery
// arithmetic (lib/Dialect/ModArith/IR/ModArithOps.td:221).
//
// Its lowering is declarative rather than C++, a DRR pattern
// (lib/Dialect/ModArith/Conversions/ModArithToArith/ModArithToArith.td:28-35):
//
//     (ModArith_SubIfGEOp $x, $y)
//       -> arith.subi $x, $y ; arith.cmpi uge, $x, $y ; arith.select
//
// so this template is a transcription of the rule itself, not of an implementation of
// it -- a smaller trusted assumption than for the C++ conversions.
//
// The source is a hole with no leakage: at the `mod_arith` level a conditional
// subtraction is a value operation with no timing meaning. The target is branchless --
// both arms are always computed and `arith.select` picks one -- so nothing becomes
// observable.
//
// Expected: CT-PRESERVING (0 -> 0). The counterpart that shows this is not vacuous is
// mod_arith_subifge_branchy.mlir: the same operation lowered with a branch instead.
builtin.module {
  func.func @source(%x: i32, %y: i32) {
    %r = "fcvd.hole"(%x, %y) {sym_name = "subifge", leaks = 0 : i64} : (i32, i32) -> i32
    func.return
  }

  func.func @target(%x: i32, %y: i32) {
    %sub = arith.subi %x, %y : i32
    %ge = arith.cmpi uge, %x, %y : i32
    %r = arith.select %ge, %sub, %x : i32
    func.return
  }
}
