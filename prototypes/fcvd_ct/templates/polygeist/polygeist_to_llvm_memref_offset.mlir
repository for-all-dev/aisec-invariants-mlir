// The falsifying twin of polygeist_to_llvm_memref.mlir: the GEP is off by one
// (`%i + 1` instead of `%i`), so the lowered code reads and writes the wrong cell. The
// address is still a deterministic function of %i, so the leakage half must PASS it
// (two runs whose source addresses agree have pinned %i, and the target's %i+1 agrees
// too); the equivalence half must refuse it -- the returned byte comes from a different
// cell, and the byte left in memory lands elsewhere.
//
// Expected: CT-PRESERVING and NOT-EQUIVALENT.
builtin.module {
  func.func @source(%m: memref<8xi8>, %i: index, %x: i8) -> i8 {
    %old = memref.load %m[%i] : memref<8xi8>
    %new = "fcvd.hole"(%old, %x) {sym_name = "BODY", leaks = 0 : i64} : (i8, i8) -> i8
    memref.store %new, %m[%i] : memref<8xi8>
    %out = memref.load %m[%i] : memref<8xi8>
    func.return %out : i8
  }

  func.func @target(%p: !llvm.ptr, %i: i64, %x: i8) -> i8 {
    %one = arith.constant 1 : i64
    %j = arith.addi %i, %one : i64
    %a = "llvm.getelementptr"(%p, %j) <{rawConstantIndices = array<i32: -1>, elem_type = i8}> : (!llvm.ptr, i64) -> !llvm.ptr
    %old = "llvm.load"(%a) <{ordering = 0 : i64}> : (!llvm.ptr) -> i8
    %new = "fcvd.hole"(%old, %x) {sym_name = "BODY", leaks = 0 : i64} : (i8, i8) -> i8
    "llvm.store"(%new, %a) <{ordering = 0 : i64}> : (i8, !llvm.ptr) -> ()
    %out = "llvm.load"(%a) <{ordering = 0 : i64}> : (!llvm.ptr) -> i8
    func.return %out : i8
  }
}
