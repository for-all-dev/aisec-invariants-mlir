// Polygeist runs mlir's `--lower-affine` at tools/cgeist/driver.cc:712. Source: the
// llvm-project submodule pinned at 26eb4285 (`git ls-tree HEAD llvm-project`),
// mlir/lib/Conversion/AffineToStandard/AffineToStandard.cpp — the submodule is not
// checked out on this box, so the file was fetched from github at that exact SHA:
//   AffineForLowering   :150-168  affine.for  -> scf.for, bounds lowered, body inlined
//   AffineLoadLowering  :345-361  affine.load -> memref.load after expandAffineMap
//   AffineStoreLowering :388-407  affine.store-> memref.store after expandAffineMap
// The maps here are the identity (d0) and a constant (${LB}) — the two shapes
// `expandAffineMap` turns into the operands themselves and an index constant.
// affine.load/store are written in xdsl's generic form (no custom syntax upstream).
//
// The body reads the cell, passes it through a hole, writes it back: the lowering must
// keep the same cells in the same order under the same guards, and must still return
// the same element.
//
// Swept (issue #63: one `0 to 3` instance said nothing about the rest): lower bound
// LB, upper bound UB and step ST of the loop, over every combination below; the memref
// is sized to the upper bound and the final read is the first cell the loop wrote. The
// pass is general over all three, the check is over these 18 -- stated, not implied.
// UB = 4 with ST = 1 exceeds the unroll bound on the scf side, so those instances are
// bounded: a too-short unrolling would show up as a difference, not hide one.
//
// Expected: CT-PRESERVING and EQUIVALENT on every instance, bounded (the scf side of
// the loop is unrolled; the affine side is exact). The falsifying twin is
// lower_affine_wrong_index.mlir, which must fail the equivalence half and only that
// half — a shifted constant index is still a deterministic address, so the trace
// cannot tell, but the returned element can.
// fcvdct.sweep LB = 0, 1
// fcvdct.sweep UB = 2, 3, 4
// fcvdct.sweep ST = 1, 2, 3
builtin.module {
  func.func @source(%m: memref<${UB}xi8>, %x: i8) -> i8 {
    affine.for %i = ${LB} to ${UB} step ${ST} {
      %old = "affine.load"(%m, %i) <{map = affine_map<(d0) -> (d0)>}> : (memref<${UB}xi8>, index) -> i8
      %new = "fcvd.hole"(%old) {sym_name = "BODY", leaks = 1 : i64} : (i8) -> i8
      "affine.store"(%new, %m, %i) <{map = affine_map<(d0) -> (d0)>}> : (i8, memref<${UB}xi8>, index) -> ()
      affine.yield
    }
    %out = "affine.load"(%m) <{map = affine_map<() -> (${LB})>}> : (memref<${UB}xi8>) -> i8
    func.return %out : i8
  }

  func.func @target(%m: memref<${UB}xi8>, %x: i8) -> i8 {
    %lb = arith.constant ${LB} : index
    %ub = arith.constant ${UB} : index
    %st = arith.constant ${ST} : index
    %first = arith.constant ${LB} : index
    scf.for %i = %lb to %ub step %st {
      %old = memref.load %m[%i] : memref<${UB}xi8>
      %new = "fcvd.hole"(%old) {sym_name = "BODY", leaks = 1 : i64} : (i8) -> i8
      memref.store %new, %m[%i] : memref<${UB}xi8>
    }
    %out = memref.load %m[%first] : memref<${UB}xi8>
    func.return %out : i8
  }
}
