// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic public-log and public-artifact sink summaries
//
// CHECK-LABEL: llvm.func @secret_logging_checkpoint_bad
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32, %[[PRIVATE:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[LOG:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[CHECKPOINT:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK: llvm.store %[[SECRET]], %[[LOG]]
// CHECK: llvm.store %[[SECRET]], %[[CHECKPOINT]]
module {
  llvm.func @secret_logging_checkpoint_bad(
      %service_account_token: i32,
      %private_state: !llvm.ptr,
      %public_log: !llvm.ptr,
      %public_checkpoint: !llvm.ptr) {
    llvm.store %service_account_token, %private_state : i32, !llvm.ptr
    // PREFLIGHT FINDING: secret written to a public log
    // secret source: %service_account_token contains authentication material
    // observable effect: log readers can inspect the value stored at %public_log
    // reason: the public store operand is exactly the secret token
    // preflight expectation: direct preflight diagnostic sink violation with a public-log summary
    llvm.store %service_account_token, %public_log : i32, !llvm.ptr
    // PREFLIGHT FINDING: secret exported in a public checkpoint
    // secret source: %service_account_token contains authentication material
    // observable effect: artifact-store readers can inspect %public_checkpoint
    // reason: serialization copies the secret into a public persistent artifact
    // preflight expectation: direct preflight diagnostic sink violation with a public-artifact summary
    llvm.store %service_account_token, %public_checkpoint : i32, !llvm.ptr
    llvm.return
  }
}
