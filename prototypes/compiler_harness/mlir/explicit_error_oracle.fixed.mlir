// RUN: %mlir-opt %s | %FileCheck %s
//
// case: explicit PKCS#1 padding error oracle
// classification: seeded-semantic-harness
// c source: ../c/explicit_error_oracle_fixed.c
// upstream GitHub source: https://github.com/openssl/openssl/blob/7fc67e0a33102aa47bbaa56533eeecb98c0450f7/crypto/rsa/rsa_pk1.c#L321-L418
// upstream revision: 7fc67e0a33102aa47bbaa56533eeecb98c0450f7
// secret: %padding_is_valid and %padding_error_detail
// input invariant: %padding_is_valid is a well-formed Boolean in {0, 1}
// public: %authorized_plaintext_length, public status, and uniform public error detail
// expected outcome: verified
// observer/model: release-relative-padding-oracle
// reason id: authorized-release-only
// outstanding obligations: none
// evidence boundary: L1 suppresses detail; L2 authorizes validity; synthetic-plaintext security is outside this L4 model
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
    // CONFIDENTIALITY REPAIR: replace the unauthorized padding detail with a constant
    // secret source: %padding_error_detail is deliberately absent from the released value
    // safe effect: callers observe error detail 0 for every secret padding failure
    // reason: %zero has no data dependence on %padding_error_detail
    // detection boundary: L1 finds no detail flow; L2 permits the separate %status release
    llvm.store %zero, %public_error_detail : i32, !llvm.ptr
    llvm.return %authorized_plaintext_length : i32
  }
}
