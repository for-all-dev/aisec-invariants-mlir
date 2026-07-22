// RUN: %mlir-opt %s | %FileCheck %s
//
// case: wrong-host FHE reveal
// classification: seeded-semantic-harness
// c source: ../c/wrong_host_fhe_reveal_fixed.c
// upstream GitHub source: https://github.com/google/heir
// upstream revision: none -- this is a policy harness, not a HEIR defect
// secret: %revealed_plaintext
// public: ciphertext handle, mailbox addresses, zero sentinel, and host policy
// expected outcome: verified
// observer/model: host-authorized-plaintext-sinks
// reason id: authorized-sink-isolation
// outstanding obligations: none
// evidence boundary: L1 host and release policy; cryptographic correctness is outside this L4 model
//
// CHECK-LABEL: llvm.func @wrong_host_fhe_reveal_fixed
// CHECK-SAME: %[[CIPHERTEXT:[a-zA-Z0-9_]+]]: i32, %[[PLAINTEXT:[a-zA-Z0-9_]+]]: i32, %[[CLIENT:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[SERVER:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK-NOT: llvm.store {{.*}}, %[[SERVER]]
// CHECK: llvm.store %[[PLAINTEXT]], %[[CLIENT]]
// CHECK-NOT: llvm.store {{.*}}, %[[SERVER]]
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK-NOT: llvm.store {{.*}}, %[[SERVER]]
// CHECK: llvm.store %[[ZERO]], %[[SERVER]]
// CHECK-NOT: llvm.store {{.*}}, %[[SERVER]]
// CHECK: llvm.return %[[CIPHERTEXT]] : i32
module {
  llvm.func @wrong_host_fhe_reveal_fixed(
      %ciphertext_handle: i32,
      %revealed_plaintext: i32,
      %authorized_client_plaintext: !llvm.ptr,
      %unauthorized_server_plaintext: !llvm.ptr) -> i32 {
    llvm.store %revealed_plaintext, %authorized_client_plaintext : i32, !llvm.ptr
    %zero = llvm.mlir.constant(0 : i32) : i32
    // CONFIDENTIALITY REPAIR: keep server storage plaintext-free
    // secret source: %revealed_plaintext remains only at the authorized client
    // removed observable: the server observes the same public zero sentinel
    // reason: %zero has no dependence on the reveal result
    // detection boundary: direct L1 host-authority and release-policy check passes
    llvm.store %zero, %unauthorized_server_plaintext : i32, !llvm.ptr
    llvm.return %ciphertext_handle : i32
  }
}
