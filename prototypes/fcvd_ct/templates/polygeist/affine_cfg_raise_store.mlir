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
// non-constant multipliers), so the invariant cannot be left symbolic. Instead of one
// constant (this template used to fix it at 3), it is SWEPT: stride S, row count R and
// column count C over every combination below, the invariant still computed by arith
// (`(S - 1) + 1`) so the fold the pass performs is exercised on each, and the memref
// sized to the last cell touched. That covers stride 1 (rows adjacent), strides
// shorter than a row (cells overlap, so the last write wins and order matters) and
// strides longer than one (gaps). The composition (`fully2ComposeAffineMapAndOperands`
// folding the feeding arith into the map) is the same code path; a proof for a
// SYMBOLIC stride stays out of reach and is recorded as such in the journal.
//
// The stored value is different on every iteration (`%x + 16*i + j`), so when a stride
// shorter than a row makes two iterations hit one cell, the check sees which write
// landed last rather than the same byte twice. (A hole over the induction variables
// would say more, but its pairwise congruence axioms do not solve in minutes at 3x3.)
//
// The observable at stake is the address obligation: the raised access must touch the
// same cell, on the same iteration, that the arith-computed one touched.
//
// Expected on every instance: CT-PRESERVING and EQUIVALENT (nothing is returned, so the memory left
// behind is the whole equivalence claim — this is the template where the memory clause
// pulls its weight). Bounded on the scf side only. The falsifying twin is
// affine_cfg_wrong_map.mlir, whose composed map has the wrong row stride and must be
// refused by the equivalence half — the addresses are deterministic either way, so the
// trace cannot tell, but the cells written can.
// fcvdct.sweep S = 1, 2, 3, 4
// fcvdct.sweep R = 1, 2, 3
// fcvdct.sweep C = 1, 2, 3
builtin.module {
  func.func @source(%m: memref<${(R - 1) * S + C}xi8>, %x: i8) {
    %ca = arith.constant ${S - 1} : index
    %cb = arith.constant 1 : index
    %inv = arith.addi %ca, %cb : index
    affine.for %i = 0 to ${R} {
      %row = arith.muli %i, %inv : index
      affine.for %j = 0 to ${C} {
        %cell = arith.addi %row, %j : index
        %c16 = arith.constant 16 : index
        %hi = arith.muli %i, %c16 : index
        %ij = arith.addi %hi, %j : index
        %tag = arith.index_cast %ij : index to i8
        %v = arith.addi %x, %tag : i8
        memref.store %v, %m[%cell] : memref<${(R - 1) * S + C}xi8>
        affine.yield
      }
      affine.yield
    }
    func.return
  }

  func.func @target(%m: memref<${(R - 1) * S + C}xi8>, %x: i8) {
    affine.for %i = 0 to ${R} {
      affine.for %j = 0 to ${C} {
        %c16 = arith.constant 16 : index
        %hi = arith.muli %i, %c16 : index
        %ij = arith.addi %hi, %j : index
        %tag = arith.index_cast %ij : index to i8
        %v = arith.addi %x, %tag : i8
        "affine.store"(%v, %m, %j, %i) <{map = affine_map<(d0, d1) -> (d0 + d1 * ${S})>}> : (i8, memref<${(R - 1) * S + C}xi8>, index, index) -> ()
        affine.yield
      }
      affine.yield
    }
    func.return
  }
}
