// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic public-log and public-artifact sink summaries
//
// CHECK-LABEL: llvm.func @secret_logging_checkpoint_fixed
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32, %[[PRIVATE:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[LOG:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[CHECKPOINT:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK-NOT: llvm.store {{.*}}, %[[LOG]]
// CHECK-NOT: llvm.store {{.*}}, %[[CHECKPOINT]]
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK-NOT: llvm.store {{.*}}, %[[LOG]]
// CHECK-NOT: llvm.store {{.*}}, %[[CHECKPOINT]]
// CHECK: llvm.store %[[ZERO]], %[[LOG]]
// CHECK-NOT: llvm.store {{.*}}, %[[LOG]]
// CHECK-NOT: llvm.store {{.*}}, %[[CHECKPOINT]]
// CHECK: llvm.store %[[ZERO]], %[[CHECKPOINT]]
// CHECK-NOT: llvm.store {{.*}}, %[[LOG]]
// CHECK-NOT: llvm.store {{.*}}, %[[CHECKPOINT]]
// CHECK: llvm.return
module {
  llvm.func @secret_logging_checkpoint_fixed(
      %service_account_token: i32,
      %private_state: !llvm.ptr,
      %public_log: !llvm.ptr,
      %public_checkpoint: !llvm.ptr) {
    llvm.store %service_account_token, %private_state : i32, !llvm.ptr
    %zero = llvm.mlir.constant(0 : i32) : i32
    // PREFLIGHT CONTROL: redact the public log field
    // secret source: %service_account_token remains only in %private_state
    // safe effect: log readers observe the same public zero sentinel
    // reason: %zero has no data dependence on the token
    // preflight expectation: direct preflight diagnostic public-log sink check passes
    llvm.store %zero, %public_log : i32, !llvm.ptr
    // PREFLIGHT CONTROL: redact the public checkpoint field
    // secret source: %service_account_token remains only in %private_state
    // safe effect: artifact readers observe the same public zero sentinel
    // reason: %zero has no data dependence on the token
    // preflight expectation: direct preflight diagnostic public-artifact sink check passes
    llvm.store %zero, %public_checkpoint : i32, !llvm.ptr
    llvm.return
  }
}
