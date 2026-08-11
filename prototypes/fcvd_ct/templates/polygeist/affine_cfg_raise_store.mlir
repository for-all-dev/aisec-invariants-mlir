// Polygeist `--affine-cfg` (pass at tools/cgeist/driver.cc:677, source
// lib/polygeist/Passes/AffineCFG.cpp): memref accesses whose indices are affine
// functions of loop ivs and loop-invariant values are raised into affine.load/store
// with the composed map — MoveStoreToAffine at :1275-1310 builds a symbol map from the
// indices and `fully2ComposeAffineMapAndOperands` folds the feeding arith into it.
//
// Transcribed from the pass's lit test test/polygeist-opt/affinecfg.mlir:3-28
// (@_Z7runTestiPPc): the store index `%j + %i * inv`, computed by arith in the source,
// becomes the composed map in the CHECK lines. Declared deviations: i32 element -> i8
// and memref<?xi32> -> memref<8xi8> (upstream's memref model stores bytes and needs a
// static shape; the pattern keys on index provenance, not the element type or extent);
// and the lit case's loop-invariant is a SYMBOL (`%j + %i * (symbol(%arg0) + 1)`) --
// a semi-affine product xdsl cannot represent at all (AffineExpr.__mul__ refuses
// non-constant multipliers), so this template instantiates the invariant at the
// constant 3. The composition (`fully2ComposeAffineMapAndOperands` folding the feeding
// arith into the map) is the same code path; its symbol half stays untranslatable
// today and is recorded as such in the journal.
//
// The observable at stake is the address obligation: the raised access must touch the
// same cell, on the same iteration, that the arith-computed one touched.
//
// Expected: CT-PRESERVING and EQUIVALENT (nothing is returned, so the memory left
// behind is the whole equivalence claim — this is the template where the memory clause
// pulls its weight). Bounded on the scf side only. The falsifying twin is
// affine_cfg_wrong_map.mlir, whose composed map has the wrong row stride and must be
// refused by the equivalence half — the addresses are deterministic either way, so the
// trace cannot tell, but the cells written can.
builtin.module {
  func.func @source(%m: memref<8xi8>, %x: i8) {
    %c2 = arith.constant 2 : index
    %c1 = arith.constant 1 : index
    %inv = arith.addi %c2, %c1 : index
    affine.for %i = 0 to 2 {
      %row = arith.muli %i, %inv : index
      affine.for %j = 0 to 2 {
        %cell = arith.addi %row, %j : index
        memref.store %x, %m[%cell] : memref<8xi8>
        affine.yield
      }
      affine.yield
    }
    func.return
  }

  func.func @target(%m: memref<8xi8>, %x: i8) {
    affine.for %i = 0 to 2 {
      affine.for %j = 0 to 2 {
        "affine.store"(%x, %m, %j, %i) <{map = affine_map<(d0, d1) -> (d0 + d1 * 3)>}> : (i8, memref<8xi8>, index, index) -> ()
        affine.yield
      }
      affine.yield
    }
    func.return
  }
}
