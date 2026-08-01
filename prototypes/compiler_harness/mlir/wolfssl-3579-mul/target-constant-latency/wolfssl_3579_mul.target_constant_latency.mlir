// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic uses an explicit configuration binding test-profile contract; it makes no real-target deployment evidence claim
// artifact status: hand-written target-call model under a synthetic test profile
//
// CHECK-LABEL: llvm.func @__muldi3
// CHECK-SAME: sps.contract_status = "test_profile_fact"
// CHECK-SAME: sps.helper_latency = "constant"
// CHECK-SAME: sps.helper_profile = "constant-latency-muldi3-test-v1"
// CHECK-SAME: sps.relevant_operands = array<i32: 0, 1>
// CHECK-LABEL: llvm.func @wolfssl_3579_mul_rv32_constant_latency_model
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i64, %[[B:[a-zA-Z0-9_]+]]: i64
// CHECK: %[[PRODUCT:[0-9]+]] = llvm.call @__muldi3(%[[A]], %[[B]])
// CHECK: llvm.return %[[PRODUCT]] : i64

module {
  llvm.func @__muldi3(%a: i64, %b: i64) -> i64 attributes {
    "sps.contract_status" = "test_profile_fact",
    "sps.helper_latency" = "constant",
    "sps.helper_profile" = "constant-latency-muldi3-test-v1",
    "sps.relevant_operands" = array<i32: 0, 1>
  }

  llvm.func @wolfssl_3579_mul_rv32_constant_latency_model(
      %secret_a: i64, %secret_b: i64) -> i64 {
    // Under this explicit synthetic profile, the call adds no timing distinction.
    %product = llvm.call @__muldi3(%secret_a, %secret_b) : (i64, i64) -> i64
    llvm.return %product : i64
  }
}
