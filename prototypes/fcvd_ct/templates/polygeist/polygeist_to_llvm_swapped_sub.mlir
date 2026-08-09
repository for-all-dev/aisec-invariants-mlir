// The falsifying twin of polygeist_to_llvm_arith.mlir: the subtraction's operands are
// exchanged (`llvm.sub %b, %prod` for `arith.subi %prod, %b`). Addition and
// multiplication would forgive this; subtraction must not. No observation exists on
// either side, so the leakage half must PASS it vacuously — the equivalence half is
// the only gate that can refuse, and must.
//
// Expected: CT-PRESERVING (vacuously) and NOT-EQUIVALENT.
builtin.module {
  func.func @source(%a: i64, %b: i64) -> i64 {
    %sum = arith.addi %a, %b : i64
    %prod = arith.muli %sum, %a : i64
    %diff = arith.subi %prod, %b : i64
    func.return %diff : i64
  }

  func.func @target(%a: i64, %b: i64) -> i64 {
    %sum = llvm.add %a, %b : i64
    %prod = llvm.mul %sum, %a : i64
    %diff = llvm.sub %b, %prod : i64
    func.return %diff : i64
  }
}
