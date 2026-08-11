// Polygeist runs mlir's `--lower-affine` at tools/cgeist/driver.cc:712. Source: the
// llvm-project submodule pinned at 26eb4285 (`git ls-tree HEAD llvm-project`),
// mlir/lib/Conversion/AffineToStandard/AffineToStandard.cpp — the submodule is not
// checked out on this box, so the file was fetched from github at that exact SHA:
//   AffineForLowering   :150-168  affine.for  -> scf.for, bounds lowered, body inlined
//   AffineLoadLowering  :345-361  affine.load -> memref.load after expandAffineMap
//   AffineStoreLowering :388-407  affine.store-> memref.store after expandAffineMap
// The maps here are the identity (d0) and a constant (1) — the two shapes
// `expandAffineMap` turns into the operands themselves and an index constant.
// affine.load/store are written in xdsl's generic form (no custom syntax upstream).
//
// The body reads the cell, passes it through a hole, writes it back: the lowering must
// keep the same cells in the same order under the same guards, and must still return
// the same element.
//
// Expected: CT-PRESERVING and EQUIVALENT, bounded (the scf side of the loop is
// unrolled; the affine side is exact). The falsifying twin is
// lower_affine_wrong_index.mlir, which must fail the equivalence half and only that
// half — a shifted constant index is still a deterministic address, so the trace
// cannot tell, but the returned element can.
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
    scf.for %i = %c0 to %c3 step %c1 {
      %old = memref.load %m[%i] : memref<4xi8>
      %new = "fcvd.hole"(%old) {sym_name = "BODY", leaks = 1 : i64} : (i8) -> i8
      memref.store %new, %m[%i] : memref<4xi8>
    }
    %out = memref.load %m[%c1] : memref<4xi8>
    func.return %out : i8
  }
}
