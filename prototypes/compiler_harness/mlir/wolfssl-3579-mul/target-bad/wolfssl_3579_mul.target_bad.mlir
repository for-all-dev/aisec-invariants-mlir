// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic under the attached configuration binding contract; applying the profile to a real helper requires deployment evidence
// artifact status: hand-written target model; generated RV32I assembly verifies only the __muldi3 call shape
// contract status: helper latency is an assumed target-profile fact, not a fact derived from this MLIR
// deployment boundary: Open until paired P4 validates the affected helper-timing profile
//
// CHECK-LABEL: llvm.func @__muldi3
// CHECK-SAME: sps.contract_status = "unverified_target_profile_assumption"
// CHECK-SAME: sps.helper_latency = "operand_dependent"
// CHECK-SAME: sps.helper_profile = "affected-rv32i-muldi3-v1"
// CHECK-SAME: sps.real_target_applicability = "deployment_evidence_required"
// CHECK-SAME: sps.relevant_operands = array<i32: 0, 1>
// CHECK-LABEL: llvm.func @wolfssl_3579_mul_rv32_bad_model
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i64, %[[B:[a-zA-Z0-9_]+]]: i64
// CHECK: %[[PRODUCT:[0-9]+]] = llvm.call @__muldi3(%[[A]], %[[B]])
// CHECK: llvm.return %[[PRODUCT]] : i64
module {
  llvm.func @__muldi3(%a: i64, %b: i64) -> i64 attributes {
    "sps.contract_status" = "unverified_target_profile_assumption",
    "sps.helper_latency" = "operand_dependent",
    "sps.helper_profile" = "affected-rv32i-muldi3-v1",
    "sps.real_target_applicability" = "deployment_evidence_required",
    "sps.relevant_operands" = array<i32: 0, 1>
  }

  llvm.func @wolfssl_3579_mul_rv32_bad_model(%secret_a: i64, %secret_b: i64) -> i64 {
    // Verified RV32I shape: i64 multiplication without M lowers to this __muldi3 call.
    // PREFLIGHT FINDING: affected-profile variable-time compiler helper
    // secret source: both operands to @__muldi3 are secret
    // observable effect: the attached affected-rv32i-muldi3-v1 contract makes helper latency operand-dependent
    // reason: both relevant operands cross into a timing-observable helper under the selected profile
    // preflight expectation: unary scanner emits a target-profile timing-risk finding; paired deployment evidence remains required
    %product = llvm.call @__muldi3(%secret_a, %secret_b) : (i64, i64) -> i64
    llvm.return %product : i64
  }
}
