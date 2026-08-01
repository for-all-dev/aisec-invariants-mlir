// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: direct preflight diagnostic host and release-policy violation
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
    // PREFLIGHT FINDING: reveal placed on an unauthorized host
    // secret source: %revealed_plaintext is the private result of the modeled reveal
    // observable effect: the server can read plaintext from its mailbox
    // reason: the server is authorized for ciphertext but not for revealed plaintext
    // preflight expectation: direct preflight diagnostic host-authority and release-policy check
    llvm.store %revealed_plaintext, %unauthorized_server_plaintext : i32, !llvm.ptr
    llvm.return %ciphertext_handle : i32
  }
}
