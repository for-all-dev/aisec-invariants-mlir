// Polygeist `--convert-polygeist-to-llvm`, the MEMORY slice (the one the arith-slice
// template left open). C-style lowering, ConvertPolygeistToLLVM.cpp:1188-1280:
//
//   memref.load  %m[%i]     ~>  %a = getelementptr %m, %i ; llvm.load  %a
//   memref.store %v,%m[%i]   ~>  %a = getelementptr %m, %i ; llvm.store %v, %a
//
// `getAddress` (:1193) emits one GEPArg per index; the memref pointer *is* the llvm
// pointer (C-style keeps no descriptor). @source takes `memref<8xi8>`, @target takes
// `!llvm.ptr` -- they lower to the same SMT value (a pointer + poison), so the two runs
// share one initial memory, and index `index` vs `i64` both lower to bv64.
//
// The body reads a cell through a hole and writes it back, so the address obligation is
// exercised on both a load and a store. The lowering must touch the same cell.
//
// Expected: CT-PRESERVING (obs equal: one load address + one store address each side)
// and EQUIVALENT (same value read, same byte left in memory). The falsifying twin is
// polygeist_to_llvm_memref_offset.mlir.
builtin.module {
  func.func @source(%m: memref<8xi8>, %i: index, %x: i8) -> i8 {
    %old = memref.load %m[%i] : memref<8xi8>
    %new = "fcvd.hole"(%old, %x) {sym_name = "BODY", leaks = 0 : i64} : (i8, i8) -> i8
    memref.store %new, %m[%i] : memref<8xi8>
    %out = memref.load %m[%i] : memref<8xi8>
    func.return %out : i8
  }

  func.func @target(%p: !llvm.ptr, %i: i64, %x: i8) -> i8 {
    %a = "llvm.getelementptr"(%p, %i) <{rawConstantIndices = array<i32: -1>, elem_type = i8}> : (!llvm.ptr, i64) -> !llvm.ptr
    %old = "llvm.load"(%a) <{ordering = 0 : i64}> : (!llvm.ptr) -> i8
    %new = "fcvd.hole"(%old, %x) {sym_name = "BODY", leaks = 0 : i64} : (i8, i8) -> i8
    "llvm.store"(%new, %a) <{ordering = 0 : i64}> : (i8, !llvm.ptr) -> ()
    %out = "llvm.load"(%a) <{ordering = 0 : i64}> : (!llvm.ptr) -> i8
    func.return %out : i8
  }
}
