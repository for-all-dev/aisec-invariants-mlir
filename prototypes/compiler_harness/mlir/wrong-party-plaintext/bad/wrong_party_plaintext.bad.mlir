// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: reduced placement/output-policy shape only; the linked hosted
// incident is not encoded by this fixture
//
// CHECK-LABEL: llvm.func @wrong_party_plaintext_bad
// CHECK-SAME: %[[PLAINTEXT:[a-zA-Z0-9_]+]]: i32, %[[AUTHORIZED:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[UNAUTHORIZED:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK: llvm.store %[[PLAINTEXT]], %[[AUTHORIZED]]
// CHECK: llvm.store %[[PLAINTEXT]], %[[UNAUTHORIZED]]
module {
  llvm.func @wrong_party_plaintext_bad(
      %plaintext: i32,
      %authorized_mailbox: !llvm.ptr,
      %unauthorized_mailbox: !llvm.ptr) {
    llvm.store %plaintext, %authorized_mailbox : i32, !llvm.ptr
    // PREFLIGHT FINDING: wrong-party plaintext store
    // secret source: %plaintext is owned by the authorized party
    // observable effect: the unauthorized party can read its mailbox contents
    // reason: this store copies the secret verbatim across the audience boundary
    // preflight expectation: direct preflight diagnostic placement and output-policy violation
    llvm.store %plaintext, %unauthorized_mailbox : i32, !llvm.ptr
    llvm.return
  }
}
