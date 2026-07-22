// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: wrong-host FHE reveal
// classification: seeded-semantic-harness
// c source: ../c/wrong_host_fhe_reveal_bad.c
// upstream GitHub source: https://github.com/google/heir
// upstream revision: none -- this is a policy harness, not a HEIR defect
// secret: %revealed_plaintext
// public: ciphertext handle, mailbox addresses, and host authority policy
// expected outcome: unsafe
// observer/model: host-authorized-plaintext-sinks
// reason id: wrong-audience-or-host
// outstanding obligations: none
// evidence boundary: direct L1 host and release-policy violation
//
// CHECK-LABEL: llvm.func @wrong_host_fhe_reveal_bad
// CHECK-SAME: %[[CIPHERTEXT:[a-zA-Z0-9_]+]]: i32, %[[PLAINTEXT:[a-zA-Z0-9_]+]]: i32, %[[CLIENT:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[SERVER:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK: llvm.store %[[PLAINTEXT]], %[[CLIENT]]
// CHECK: llvm.store %[[PLAINTEXT]], %[[SERVER]]
module {
  llvm.func @wrong_host_fhe_reveal_bad(
      %ciphertext_handle: i32,
      %revealed_plaintext: i32,
      %authorized_client_plaintext: !llvm.ptr,
      %unauthorized_server_plaintext: !llvm.ptr) -> i32 {
    llvm.store %revealed_plaintext, %authorized_client_plaintext : i32, !llvm.ptr
    // CONFIDENTIALITY ERROR: reveal placed on an unauthorized host
    // secret source: %revealed_plaintext is the private result of the modeled reveal
    // observable effect: the server can read plaintext from its mailbox
    // reason: the server is authorized for ciphertext but not for revealed plaintext
    // detection boundary: direct L1 host-authority and release-policy check
    // expected-error @+1 {{wrong-audience-or-host}}
    llvm.store %revealed_plaintext, %unauthorized_server_plaintext : i32, !llvm.ptr
    llvm.return %ciphertext_handle : i32
  }
}
