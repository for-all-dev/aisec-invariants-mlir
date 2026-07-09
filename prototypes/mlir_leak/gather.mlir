// idx_gather: out[i] = table[ idx[i] ]   idx is the secret
// Source-oblivious MEMORY/ADDRESS case. A pure functional map at source level;
// lowering materializes a secret-dependent load address (memref.load %table[%j]
// with %j derived from the secret). memcheck reports the address dependence;
// Dr/Dw cache footprint separates the classes. Most likely genuine positive.
func.func @idx_gather(%idx: memref<4096xi32>,
                      %table: memref<256xf32>,
                      %out: memref<4096xf32>) {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %n  = arith.constant 4096 : index
  scf.for %i = %c0 to %n step %c1 {
    %j32 = memref.load %idx[%i] : memref<4096xi32>
    %j = arith.index_cast %j32 : i32 to index
    %v = memref.load %table[%j] : memref<256xf32>   // address depends on secret
    memref.store %v, %out[%i] : memref<4096xf32>
    scf.yield
  }
  return
}
