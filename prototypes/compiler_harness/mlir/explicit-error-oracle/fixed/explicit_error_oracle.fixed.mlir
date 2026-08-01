// RUN: %mlir-opt %s | %FileCheck %s
//
// input invariant: %padding_is_valid is a well-formed Boolean in {0, 1}
// scope note: the preflight suppresses detail; the exact product models only
// the sanctioned validity release, not synthetic-plaintext security
//
// CHECK-LABEL: llvm.func @explicit_error_oracle_fixed
// CHECK-SAME: %[[VALID:[a-zA-Z0-9_]+]]: i32, %[[DETAIL:[a-zA-Z0-9_]+]]: i32, %[[LENGTH:[a-zA-Z0-9_]+]]: i32, %[[STATUS_SINK:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[DETAIL_SINK:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK-NOT: llvm.store {{.*}}, %[[STATUS_SINK]]
// CHECK-NOT: llvm.store {{.*}}, %[[DETAIL_SINK]]
// CHECK: %[[ONE:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[VALID_BIT:[0-9]+]] = llvm.and %[[VALID]], %[[ONE]]
// CHECK: %[[STATUS:[0-9]+]] = llvm.xor %[[VALID_BIT]], %[[ONE]]
// CHECK-NOT: llvm.store {{.*}}, %[[STATUS_SINK]]
// CHECK-NOT: llvm.store {{.*}}, %[[DETAIL_SINK]]
// CHECK: llvm.store %[[STATUS]], %[[STATUS_SINK]] {sps.release_policy = "padding_validity_v1"}
// CHECK-NOT: llvm.store {{.*}}, %[[STATUS_SINK]]
// CHECK-NOT: llvm.store {{.*}}, %[[DETAIL_SINK]]
// CHECK: llvm.store %[[ZERO]], %[[DETAIL_SINK]]
// CHECK-NOT: llvm.store {{.*}}, %[[STATUS_SINK]]
// CHECK-NOT: llvm.store {{.*}}, %[[DETAIL_SINK]]
// CHECK: llvm.return %[[LENGTH]] : i32
module {
  llvm.func @explicit_error_oracle_fixed(
      %padding_is_valid: i32,
      %padding_error_detail: i32,
      %authorized_plaintext_length: i32,
      %public_status: !llvm.ptr,
      %public_error_detail: !llvm.ptr) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %zero = llvm.mlir.constant(0 : i32) : i32
    %valid_bit = llvm.and %padding_is_valid, %one : i32
    %status = llvm.xor %valid_bit, %one : i32
    // SANCTIONED RELEASE: preserve exactly the authorized valid/invalid bit.
    llvm.store %status, %public_status {
      "sps.release_policy" = "padding_validity_v1"
    } : i32, !llvm.ptr
    // PREFLIGHT CONTROL: replace the unauthorized padding detail with a constant
    // secret source: %padding_error_detail is deliberately absent from the released value
    // safe effect: callers observe error detail 0 for every secret padding failure
    // reason: %zero has no data dependence on %padding_error_detail
    // preflight expectation: unary scanner sees only the fixed public-detail value
    llvm.store %zero, %public_error_detail : i32, !llvm.ptr
    llvm.return %authorized_plaintext_length : i32
  }
}
