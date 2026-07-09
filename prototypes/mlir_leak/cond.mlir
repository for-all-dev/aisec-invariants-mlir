// cond_reduce: s = sum(w); if s > 0 write 1.0 else 2.0
// Authored-branch positive control. A reduction of the secret feeds an scf.if,
// which lowers (convert-scf-to-cf) to a cf.cond_br on a secret-derived value ->
// memcheck taint must fire in EVERY pipeline. Class A = zeros (else), B = ones (if).
func.func @cond_reduce(%w: memref<4096xf32>, %out: memref<1xf32>) {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %n  = arith.constant 4096 : index
  %z  = arith.constant 0.0 : f32
  %s = scf.for %i = %c0 to %n step %c1 iter_args(%acc = %z) -> (f32) {
    %v = memref.load %w[%i] : memref<4096xf32>
    %a = arith.addf %acc, %v : f32
    scf.yield %a : f32
  }
  %pos = arith.cmpf ogt, %s, %z : f32
  scf.if %pos {
    %one = arith.constant 1.0 : f32
    memref.store %one, %out[%c0] : memref<1xf32>
  } else {
    %two = arith.constant 2.0 : f32
    memref.store %two, %out[%c0] : memref<1xf32>
  }
  return
}
