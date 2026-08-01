// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: reduced placement/output-policy shape only; the linked hosted
// incident is not encoded by this fixture
//
// CHECK-LABEL: llvm.func @wrong_party_plaintext_fixed
// CHECK-SAME: %[[PLAINTEXT:[a-zA-Z0-9_]+]]: i32, %[[AUTHORIZED:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[UNAUTHORIZED:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK-NOT: llvm.store {{.*}}, %[[UNAUTHORIZED]]
// CHECK: llvm.store %[[PLAINTEXT]], %[[AUTHORIZED]]
// CHECK-NOT: llvm.store {{.*}}, %[[UNAUTHORIZED]]
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK-NOT: llvm.store {{.*}}, %[[UNAUTHORIZED]]
// CHECK: llvm.store %[[ZERO]], %[[UNAUTHORIZED]]
// CHECK-NOT: llvm.store {{.*}}, %[[UNAUTHORIZED]]
// CHECK: llvm.return
module {
  llvm.func @wrong_party_plaintext_fixed(
      %plaintext: i32,
      %authorized_mailbox: !llvm.ptr,
      %unauthorized_mailbox: !llvm.ptr) {
    llvm.store %plaintext, %authorized_mailbox : i32, !llvm.ptr
    %zero = llvm.mlir.constant(0 : i32) : i32
    // PREFLIGHT CONTROL: redact the unauthorized mailbox
    // secret source: %plaintext remains available only to the authorized party
    // safe effect: the unauthorized party observes the same public zero sentinel
    // reason: the stored value has no data dependence on %plaintext
    // preflight expectation: direct preflight diagnostic placement and output-policy check passes
    llvm.store %zero, %unauthorized_mailbox : i32, !llvm.ptr
    llvm.return
  }
}
