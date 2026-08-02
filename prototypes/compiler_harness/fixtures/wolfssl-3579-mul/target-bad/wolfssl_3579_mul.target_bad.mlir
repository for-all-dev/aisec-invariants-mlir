// RUN: %checkpoint-runner run --snapshot fixtures/wolfssl-3579-mul/target-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wolfssl-3579-mul/target-bad/wolfssl_3579_mul.target_bad.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic under the attached configuration binding contract; applying the profile to a real helper requires deployment evidence
// artifact status: hand-written target model; generated RV32I assembly verifies only the __muldi3 call shape
// contract status: helper latency is an assumed target-profile fact, not a fact derived from this MLIR
// deployment boundary: Open until paired P4 validates the affected helper-timing profile
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @__muldi3(%a: i64, %b: i64) -> i64 attributes {
    "sps.contract_status" = "unverified_target_profile_assumption",
    "sps.helper_latency" = "operand_dependent",
    "sps.helper_profile" = "affected-rv32i-muldi3-v2",
    "sps.real_target_applicability" = "deployment_evidence_required",
    "sps.relevant_operands" = array<i32: 0, 1>
  }

  llvm.func @wolfssl_3579_mul_rv32_bad_model(
      %secret_a: i64 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %secret_b: i64 {sps.fixture_refs = ["snapshot.secret[1]"], sps.label = "high"}) -> i64 {
    // Verified RV32I shape: i64 multiplication without M lowers to this __muldi3 call.
    // PREFLIGHT FINDING: affected-profile variable-time compiler helper
    // secret source: both operands to @__muldi3 are secret
    // observable effect: the attached affected-rv32i-muldi3-v2 contract makes helper latency operand-dependent
    // reason: both relevant operands cross into a timing-observable helper under the selected profile
    // preflight expectation: unary scanner emits a target-profile timing-risk finding; paired deployment evidence remains required
    %product = llvm.call @__muldi3(%secret_a, %secret_b) {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"],
      sps.observable_candidate = ["control", "timing"]
    } : (i64, i64) -> i64
    llvm.return %product : i64
  }
}
