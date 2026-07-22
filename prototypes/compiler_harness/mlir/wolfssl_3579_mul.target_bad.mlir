// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: wolfssl/CVE-2026-3579
// classification: modeled-from-verified-assembly
// c source: ../c/wolfssl_3579_mul_vulnerable.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
// upstream revision: b6fbfad945d4b98fce619b6e5b6561b3eca1205b
// secret: %secret_a and %secret_b
// public: selected target profile affected-rv32i-muldi3-v1
// expected outcome: unsafe
// observer/model: affected-rv32i-muldi3-v1
// reason id: secret-dependent-variable-latency-call
// outstanding obligations: none
// evidence boundary: L1 under the attached L0 contract; applying the profile to a real helper requires L4 evidence
// artifact status: hand-written target model; generated RV32I assembly verifies only the __muldi3 call shape
// contract status: helper latency is an assumed target-profile fact, not a fact derived from this MLIR
// real-target applicability: conditional until L4 validates the affected helper-timing profile
//
// CHECK-LABEL: llvm.func @__muldi3
// CHECK-SAME: sps.contract_status = "assumed_l0_target_fact"
// CHECK-SAME: sps.helper_latency = "operand_dependent"
// CHECK-SAME: sps.helper_profile = "affected-rv32i-muldi3-v1"
// CHECK-SAME: sps.real_target_applicability = "requires_l4_evidence"
// CHECK-SAME: sps.relevant_operands = array<i32: 0, 1>
// CHECK-LABEL: llvm.func @wolfssl_3579_mul_rv32_bad_model
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i64, %[[B:[a-zA-Z0-9_]+]]: i64
// CHECK: %[[PRODUCT:[0-9]+]] = llvm.call @__muldi3(%[[A]], %[[B]])
// CHECK: llvm.return %[[PRODUCT]] : i64
module {
  llvm.func @__muldi3(%a: i64, %b: i64) -> i64 attributes {
    "sps.contract_status" = "assumed_l0_target_fact",
    "sps.helper_latency" = "operand_dependent",
    "sps.helper_profile" = "affected-rv32i-muldi3-v1",
    "sps.real_target_applicability" = "requires_l4_evidence",
    "sps.relevant_operands" = array<i32: 0, 1>
  }

  llvm.func @wolfssl_3579_mul_rv32_bad_model(%secret_a: i64, %secret_b: i64) -> i64 {
    // Verified RV32I shape: i64 multiplication without M lowers to this __muldi3 call.
    // CONFIDENTIALITY ERROR: affected-profile variable-time compiler helper
    // secret source: both operands to @__muldi3 are secret
    // observable effect: the attached affected-rv32i-muldi3-v1 contract makes helper latency operand-dependent
    // reason: both relevant operands cross into a timing-observable helper under the selected profile
    // detection boundary: L1 reports unsafe from the attached L0 contract; without any helper summary the result is unknown, while proving it is L4
    // expected-error @+1 {{secret-dependent-variable-latency-call}}
    %product = llvm.call @__muldi3(%secret_a, %secret_b) : (i64, i64) -> i64
    llvm.return %product : i64
  }
}
