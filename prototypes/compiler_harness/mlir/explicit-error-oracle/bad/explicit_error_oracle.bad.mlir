// RUN: %mlir-opt %s | %FileCheck %s
//
// input invariant: %padding_is_valid is a well-formed Boolean in {0, 1}
// scope note: preflight diagnostic for the extra detail; exact product holds the sanctioned validity bit fixed
//
// CHECK-LABEL: llvm.func @explicit_error_oracle_bad
// CHECK-SAME: %[[VALID:[a-zA-Z0-9_]+]]: i32, %[[DETAIL:[a-zA-Z0-9_]+]]: i32, %[[LENGTH:[a-zA-Z0-9_]+]]: i32, %[[STATUS_SINK:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[DETAIL_SINK:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK: %[[ONE:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[VALID_BIT:[0-9]+]] = llvm.and %[[VALID]], %[[ONE]]
// CHECK: %[[STATUS:[0-9]+]] = llvm.xor %[[VALID_BIT]], %[[ONE]]
// CHECK: llvm.store %[[STATUS]], %[[STATUS_SINK]] {sps.release_policy = "padding_validity_v1"}
// CHECK: llvm.store %[[DETAIL]], %[[DETAIL_SINK]]
module {
  llvm.func @explicit_error_oracle_bad(
      %padding_is_valid: i32,
      %padding_error_detail: i32,
      %authorized_plaintext_length: i32,
      %public_status: !llvm.ptr,
      %public_error_detail: !llvm.ptr) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %valid_bit = llvm.and %padding_is_valid, %one : i32
    %status = llvm.xor %valid_bit, %one : i32
    // SANCTIONED RELEASE: %public_status may reveal the valid/invalid bit.
    llvm.store %status, %public_status {
      "sps.release_policy" = "padding_validity_v1"
    } : i32, !llvm.ptr
    // PREFLIGHT FINDING: padding detail exceeds the sanctioned validity release
    // secret source: %padding_error_detail identifies a specific secret padding failure
    // observable effect: a caller reads the secret diagnostic from %public_error_detail
    // reason: equal validity bits with different padding details produce different public outputs
    // preflight expectation: unary scanner flags the unauthorized public-detail store
    llvm.store %padding_error_detail, %public_error_detail : i32, !llvm.ptr
    llvm.return %authorized_plaintext_length : i32
  }
}
