// The falsifying twin of lower_affine_for_load_store.mlir: the final load's expanded
// map is off by one — cell 2 instead of cell 1. A wrong constant address is still a
// deterministic address, so the leakage half must PASS this (the trace of one run
// determines the other's); the equivalence half must refuse it, because the loop leaves
// BODY(m[1]) and BODY(m[2]) in different cells and the initial memory is free.
//
// Expected: CT-PRESERVING and NOT-EQUIVALENT.
builtin.module {
  func.func @source(%m: memref<4xi8>, %x: i8) -> i8 {
    affine.for %i = 0 to 3 {
      %old = "affine.load"(%m, %i) <{map = affine_map<(d0) -> (d0)>}> : (memref<4xi8>, index) -> i8
      %new = "fcvd.hole"(%old) {sym_name = "BODY", leaks = 1 : i64} : (i8) -> i8
      "affine.store"(%new, %m, %i) <{map = affine_map<(d0) -> (d0)>}> : (i8, memref<4xi8>, index) -> ()
      affine.yield
    }
    %out = "affine.load"(%m) <{map = affine_map<() -> (1)>}> : (memref<4xi8>) -> i8
    func.return %out : i8
  }

  func.func @target(%m: memref<4xi8>, %x: i8) -> i8 {
    %c0 = arith.constant 0 : index
    %c3 = arith.constant 3 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    scf.for %i = %c0 to %c3 step %c1 {
      %old = memref.load %m[%i] : memref<4xi8>
      %new = "fcvd.hole"(%old) {sym_name = "BODY", leaks = 1 : i64} : (i8) -> i8
      memref.store %new, %m[%i] : memref<4xi8>
    }
    %out = memref.load %m[%c2] : memref<4xi8>
    func.return %out : i8
  }
}
