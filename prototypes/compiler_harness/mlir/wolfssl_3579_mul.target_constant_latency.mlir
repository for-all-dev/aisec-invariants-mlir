// RUN: %mlir-opt %s | %FileCheck %s
//
// case: wolfssl/CVE-2026-3579 under a constant-latency helper test profile
// classification: modeled-test-profile
// c source: ../c/wolfssl_3579_mul_vulnerable.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
// upstream revision: b6fbfad945d4b98fce619b6e5b6561b3eca1205b
// secret: %secret_a and %secret_b
// public: selected target profile constant-latency-muldi3-test-v1
// expected outcome: verified
// observer/model: constant-latency-muldi3-test-v1
// reason id: constant-latency-helper-contract
// outstanding obligations: none
// evidence boundary: L1 uses an explicit L0 test-profile contract; it makes no real-target L4 claim
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
