// HEIR `--tensor-ext-to-tensor` for `tensor_ext.rotate` -- the cyclic rotation that FHE
// packing is built on (lib/Dialect/TensorExt/IR/TensorExtOps.td:21) -- in the case where
// the rotation amount is an SSA value rather than a constant.
//
// Transcribed from the pattern (lib/Dialect/TensorExt/Conversions/TensorExtToTensor/
// TensorExtToTensor.cpp:68-81, :147-162) and confirmed against the pass's own test
// (tests/Dialect/TensorExt/Conversions/tensor_ext_to_tensor/rotate_dynamic.mlir), which
// CHECKs exactly this sequence:
//
//     %v0 = arith.remsi %shift, %c16      // normalise the shift into [0, N)
//     %v1 = arith.addi  %v0, %c16
//     %v2 = arith.remsi %v1, %c16
//     %v3 = arith.subi  %c16, %v2
//     two tensor.extract_slice, two tensor.insert_slice, at those offsets
//
// The source is a hole with no leakage: at the `tensor_ext` level a rotation is a value
// operation, and in an FHE backend it is one ciphertext operation whose cost does not
// depend on the data. The slices in the target are holes too, because `extract_slice`
// and `insert_slice` have no semantics here -- so the observation count below is a
// **lower bound**: a bufferised slice at a data-dependent offset would add address
// observations on top, and the verdict can only get worse, never better.
//
// Expected: CT-BREAKING (0 -> 4). Normalising the shift costs two signed remainders,
// and on x86 `idiv` latency depends on its operands. This matters when the rotation
// amount is private. In an arithmetic FHE backend it is not -- Galois keys are
// generated per rotation amount, so amounts are public by construction -- but this
// lowering is the *plaintext* path, where nothing enforces that.
builtin.module {
  func.func @source(%t: tensor<16xi32>, %shift: index) {
    %r = "fcvd.hole"(%t, %shift) {sym_name = "rotate", leaks = 0 : i64}
       : (tensor<16xi32>, index) -> tensor<16xi32>
    func.return
  }

  func.func @target(%t: tensor<16xi32>, %shift: index) {
    %c16 = arith.constant 16 : index
    %v0 = arith.remsi %shift, %c16 : index
    %v1 = arith.addi %v0, %c16 : index
    %v2 = arith.remsi %v1, %c16 : index
    %v3 = arith.subi %c16, %v2 : index
    %left = "fcvd.hole"(%t, %v2) {sym_name = "extract_left", leaks = 0 : i64}
          : (tensor<16xi32>, index) -> tensor<16xi32>
    %right = "fcvd.hole"(%t, %v2, %v3) {sym_name = "extract_right", leaks = 0 : i64}
           : (tensor<16xi32>, index, index) -> tensor<16xi32>
    %ins_left = "fcvd.hole"(%left, %t, %v3, %v2) {sym_name = "insert_left", leaks = 0 : i64}
              : (tensor<16xi32>, tensor<16xi32>, index, index) -> tensor<16xi32>
    %ins_right = "fcvd.hole"(%right, %ins_left, %v3) {sym_name = "insert_right", leaks = 0 : i64}
               : (tensor<16xi32>, tensor<16xi32>, index) -> tensor<16xi32>
    func.return
  }
}
