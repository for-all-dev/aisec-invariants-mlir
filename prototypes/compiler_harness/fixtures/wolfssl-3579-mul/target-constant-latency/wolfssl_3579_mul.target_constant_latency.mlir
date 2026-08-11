// RUN: %checkpoint-runner run --snapshot fixtures/wolfssl-3579-mul/target-constant-latency/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wolfssl-3579-mul/target-constant-latency/wolfssl_3579_mul.target_constant_latency.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic uses an explicit configuration binding test-profile contract; it makes no real-target deployment evidence claim
// artifact status: hand-written target-call model under a synthetic test profile
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//

module {
  llvm.func @__muldi3(%a: i64, %b: i64) -> i64 attributes {
    "sps.contract_status" = "test_profile_fact",
    "sps.helper_latency" = "constant",
    "sps.helper_profile" = "constant-latency-muldi3-test-v2",
    "sps.relevant_operands" = array<i32: 0, 1>
  }

  llvm.func @wolfssl_3579_mul_rv32_constant_latency_model(
      %secret_a: i64 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %secret_b: i64 {sps.fixture_refs = ["snapshot.secret[1]"], sps.label = "high"}) -> i64 {
    // Under this explicit synthetic profile, the call adds no timing distinction.
    %product = llvm.call @__muldi3(%secret_a, %secret_b) {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["timing"]
    } : (i64, i64) -> i64
    llvm.return %product : i64
  }
}
