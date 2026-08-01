// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic sees a secret-dependent helper call; helper timing must be supplied through deployment evidence
// artifact status: hand-written target-call model; no helper timing is assumed
//
// CHECK-LABEL: llvm.func @__muldi3
// CHECK-NOT: sps.helper_latency
// CHECK-LABEL: llvm.func @wolfssl_3579_mul_rv32_unknown_model
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i64, %[[B:[a-zA-Z0-9_]+]]: i64
// CHECK: %[[PRODUCT:[0-9]+]] = llvm.call @__muldi3(%[[A]], %[[B]])
// CHECK: llvm.return %[[PRODUCT]] : i64

module {
  llvm.func @__muldi3(%a: i64, %b: i64) -> i64

  llvm.func @wolfssl_3579_mul_rv32_unknown_model(
      %secret_a: i64, %secret_b: i64) -> i64 {
    // No timing conclusion follows until the external helper has a target contract.
    %product = llvm.call @__muldi3(%secret_a, %secret_b) : (i64, i64) -> i64
    llvm.return %product : i64
  }
}
