// dynshape: the secret is an extent k in [0,4096]. Allocate a DYNAMIC buffer of
// size k and do O(k) work over it. The dynamic extent = secret, so both the
// memref.alloc(%k) size and the scf.for trip count are secret-dependent -- the
// dynamic-shape channel the proposal names. Output is a fixed-shape scalar; only
// the internal dynamic buffer / loop bound carry the secret.
// Classes: A k=1 (tiny), B k=4096 (full) -> Ir/Dw and the loop-bound branch leak.
func.func @dynshape(%kbuf: memref<1xi32>, %out: memref<1xf32>) {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %z = arith.constant 0.0 : f32
  %one = arith.constant 1.0 : f32
  %k32 = memref.load %kbuf[%c0] : memref<1xi32>
  %k = arith.index_cast %k32 : i32 to index        // secret-derived extent
  %buf = memref.alloc(%k) : memref<?xf32>            // secret-SIZED allocation
  %s = scf.for %j = %c0 to %k step %c1 iter_args(%acc = %z) -> (f32) {
    memref.store %one, %buf[%j] : memref<?xf32>       // O(k) work, k = secret
    %a = arith.addf %acc, %one : f32
    scf.yield %a : f32
  }
  memref.store %s, %out[%c0] : memref<1xf32>
  memref.dealloc %buf : memref<?xf32>
  return
}
