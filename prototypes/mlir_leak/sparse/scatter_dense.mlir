// Oblivious DENSE reference for scatter.mlir -- the baseline the sparsified
// build is judged against.
//
// Same signature (after lowering, the same standard memref ABI
// sparse_driver.c already calls) and the same mathematical result:
//   out[p] = sum_k (crd[k] == p) ? vals[k] : 0
// computed by visiting EVERY (dense position, stored entry) pair.
//
// Why this shape, and not `arith.select` or a data-dependent write:
//   - trip counts are compile-time constants (256 x 8), so the amount of
//     work cannot depend on the pattern;
//   - every address is loop-derived (crd[k], vals[k], out[p]) -- the secret
//     is never an address, which is precisely the channel --sparsification
//     introduces;
//   - the secret reaches only a compare folded into ARITHMETIC
//     (cmpi -> uitofp -> mulf), never a select or a branch. That matters at
//     -O0: this study's own core sweep found that an `arith.select` on a
//     secret is lowered by the -O0 instruction selector into a conditional
//     BRANCH (mask_select, taint:cf), which would make the "oblivious"
//     baseline leak for a reason that has nothing to do with sparsity.
func.func @scatter(%vals: memref<8xf32>,
                   %pos: memref<2xindex>,
                   %crd: memref<8xindex>) -> memref<256xf32> {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %c8 = arith.constant 8 : index
  %c256 = arith.constant 256 : index
  %zero = arith.constant 0.0 : f32

  %out = memref.alloc() : memref<256xf32>

  scf.for %p = %c0 to %c256 step %c1 {
    %acc = scf.for %k = %c0 to %c8 step %c1 iter_args(%a = %zero) -> (f32) {
      %c = memref.load %crd[%k] : memref<8xindex>
      %v = memref.load %vals[%k] : memref<8xf32>
      %eq = arith.cmpi eq, %c, %p : index
      %m = arith.uitofp %eq : i1 to f32
      %prod = arith.mulf %v, %m : f32
      %na = arith.addf %a, %prod : f32
      scf.yield %na : f32
    }
    memref.store %acc, %out[%p] : memref<256xf32>
  }

  return %out : memref<256xf32>
}
