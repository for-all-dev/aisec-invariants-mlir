// Second control for the GEP leakage rule: here the index IS the secret, and the
// lowering is faithful. The point is not the lowering (it is correct) but the checker:
// if llvm.getelementptr did not leak its index, this would come back CT-PRESERVING and
// the memref->llvm address channel would be invisible. It must come back CT-BREAKING on
// the address obligation -- the proof that the new leakage rule is load-bearing, not
// decoration. (A self-composition kernel, not a lowering pair: source == target, the
// secret steers the address on both sides.)
//
// Expected: CT-BREAKING (address), because a secret index moves the GEP on both runs.
builtin.module {
  func.func @source(%p: !llvm.ptr, %s: i64 {fcvdct.secret}) -> i8 {
    %a = "llvm.getelementptr"(%p, %s) <{rawConstantIndices = array<i32: -1>, elem_type = i8}> : (!llvm.ptr, i64) -> !llvm.ptr
    %v = "llvm.load"(%a) <{ordering = 0 : i64}> : (!llvm.ptr) -> i8
    func.return %v : i8
  }

  func.func @target(%p: !llvm.ptr, %s: i64 {fcvdct.secret}) -> i8 {
    %a = "llvm.getelementptr"(%p, %s) <{rawConstantIndices = array<i32: -1>, elem_type = i8}> : (!llvm.ptr, i64) -> !llvm.ptr
    %v = "llvm.load"(%a) <{ordering = 0 : i64}> : (!llvm.ptr) -> i8
    func.return %v : i8
  }
}
