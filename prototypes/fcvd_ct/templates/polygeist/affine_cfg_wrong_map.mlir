// The falsifying twin of affine_cfg_raise_store.mlir: the composed map has the wrong
// row stride — `d0 + d1 * 2` where the source computes `%j + %i * 3`. Both are
// deterministic, so the leakage half must PASS this; the equivalence half must refuse
// it: on the second row the cells written differ, and nothing is returned, so the
// memory left behind is the entire claim.
//
// Expected: CT-PRESERVING and NOT-EQUIVALENT.
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
        "affine.store"(%x, %m, %j, %i) <{map = affine_map<(d0, d1) -> (d0 + d1 * 2)>}> : (i8, memref<8xi8>, index, index) -> ()
        affine.yield
      }
      affine.yield
    }
    func.return
  }
}
