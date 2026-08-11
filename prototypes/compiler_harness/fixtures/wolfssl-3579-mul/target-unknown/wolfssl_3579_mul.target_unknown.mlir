// RUN: %checkpoint-runner run --snapshot fixtures/wolfssl-3579-mul/target-unknown/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wolfssl-3579-mul/target-unknown/wolfssl_3579_mul.target_unknown.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic sees a secret-dependent helper call; helper timing must be supplied through deployment evidence
// artifact status: hand-written target-call model; no helper timing is assumed
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//

module {
  llvm.func @__muldi3(%a: i64, %b: i64) -> i64

  llvm.func @wolfssl_3579_mul_rv32_unknown_model(
      %secret_a: i64 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %secret_b: i64 {sps.fixture_refs = ["snapshot.secret[1]"], sps.label = "high"}) -> i64 {
    // No timing conclusion follows until the external helper has a target contract.
    %product = llvm.call @__muldi3(%secret_a, %secret_b) {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["timing"]
    } : (i64, i64) -> i64
    llvm.return %product : i64
  }
}
