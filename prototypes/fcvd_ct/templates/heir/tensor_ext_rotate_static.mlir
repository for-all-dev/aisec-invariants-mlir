// The same lowering when the rotation amount is a compile-time constant. The pass folds
// the normalisation itself (TensorExtToTensor.cpp:61-67), so no arithmetic on the shift
// is emitted at all -- confirmed by its own test rotate_static.mlir, whose CHECK lines
// contain only `tensor.extract_slice` and `tensor.insert_slice` at literal offsets.
//
// Expected: CT-PRESERVING (0 -> 0). Paired with tensor_ext_rotate_dynamic.mlir this
// says where the line runs: it is not rotation that costs anything, it is a rotation
// amount the compiler cannot see.
builtin.module {
  func.func @source(%t: tensor<16xi32>) {
    %r = "fcvd.hole"(%t) {sym_name = "rotate_by_1", leaks = 0 : i64}
       : (tensor<16xi32>) -> tensor<16xi32>
    func.return
  }

  func.func @target(%t: tensor<16xi32>) {
    %left = "fcvd.hole"(%t) {sym_name = "extract_left", leaks = 0 : i64}
          : (tensor<16xi32>) -> tensor<16xi32>
    %right = "fcvd.hole"(%t) {sym_name = "extract_right", leaks = 0 : i64}
           : (tensor<16xi32>) -> tensor<16xi32>
    %ins_left = "fcvd.hole"(%left, %t) {sym_name = "insert_left", leaks = 0 : i64}
              : (tensor<16xi32>, tensor<16xi32>) -> tensor<16xi32>
    %ins_right = "fcvd.hole"(%right, %ins_left) {sym_name = "insert_right", leaks = 0 : i64}
               : (tensor<16xi32>, tensor<16xi32>) -> tensor<16xi32>
    func.return
  }
}
