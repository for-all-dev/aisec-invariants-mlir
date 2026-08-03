// The control for mod_arith_subifge_to_arith.mlir: the same `mod_arith.subifge`, but
// lowered the way one would write it by hand in C -- as a branch. HEIR does *not* do
// this; the point of the file is that if it did, the checker would say so, which is
// what makes the CT-PRESERVING verdict on the real lowering worth anything.
//
// Expected: CT-BREAKING (0 -> 1). The comparison becomes a path condition, and on a
// reduction step the compared value is the secret residue.
builtin.module {
  func.func @source(%x: i32, %y: i32) {
    %r = "fcvd.hole"(%x, %y) {sym_name = "subifge", leaks = 0 : i64} : (i32, i32) -> i32
    func.return
  }

  func.func @target(%x: i32, %y: i32) {
    %ge = arith.cmpi uge, %x, %y : i32
    %r = scf.if %ge -> (i32) {
      %sub = arith.subi %x, %y : i32
      scf.yield %sub : i32
    } else {
      scf.yield %x : i32
    }
    func.return
  }
}
