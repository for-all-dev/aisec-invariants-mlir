// mask_select: out[i] = mask[i]!=0 ? a[i] : b[i]
// Source-oblivious control-flow case. Branchless arith.select on a secret-derived
// mask. Question: does any lowering (linalg->loops, canonicalize, vectorize) turn
// this into data-dependent control flow? Prior expectation: arith.select ->
// llvm.select (cmov/blend) stays branchless, so a NEGATIVE here is a real result.
// Named mask_select (not `select`) to avoid the libc select(2) symbol.
#id = affine_map<(d0) -> (d0)>
func.func @mask_select(%mask: memref<4096xi8>,
                       %a: memref<4096xf32>, %b: memref<4096xf32>,
                       %out: memref<4096xf32>) {
  linalg.generic {
    indexing_maps = [#id, #id, #id, #id],
    iterator_types = ["parallel"]
  } ins(%mask, %a, %b : memref<4096xi8>, memref<4096xf32>, memref<4096xf32>)
    outs(%out : memref<4096xf32>) {
  ^bb0(%m: i8, %av: f32, %bv: f32, %o: f32):
    %zero = arith.constant 0 : i8
    %c = arith.cmpi ne, %m, %zero : i8
    %s = arith.select %c, %av, %bv : f32
    linalg.yield %s : f32
  }
  return
}
