// RUN: %mlir-opt %s | %FileCheck %s
//
// case: wolfssl/CVE-2026-3579 helper call without a timing summary
// classification: modeled-helper-call-without-contract
// c source: ../c/wolfssl_3579_mul_vulnerable.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
// upstream revision: b6fbfad945d4b98fce619b6e5b6561b3eca1205b
// secret: %secret_a and %secret_b
// public: RV32I helper timing observer
// expected outcome: unknown
// observer/model: rv32i-helper-timing
// reason id: missing-helper-contract
// outstanding obligations: helper-latency-contract
// evidence boundary: L1 sees a secret-dependent helper call; helper timing must be supplied at L4
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
