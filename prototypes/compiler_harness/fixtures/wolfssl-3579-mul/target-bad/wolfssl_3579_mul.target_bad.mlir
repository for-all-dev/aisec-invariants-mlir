// RUN: %checkpoint-runner run --snapshot fixtures/wolfssl-3579-mul/target-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wolfssl-3579-mul/target-bad/wolfssl_3579_mul.target_bad.mlir --records %t.checkpoints

//
// scope note: synthetic target-control oracle; applying this shape to a real
// helper still requires deployment evidence
// artifact status: hand-written target model; generated RV32I assembly verifies
// only the __muldi3 call shape
// deployment boundary: Open until P4 evidence binds the actual helper body
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @wolfssl_3579_mul_rv32_bad_model(
      %secret_a: i64 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %secret_b: i64 {sps.fixture_refs = ["snapshot.secret[1]"], sps.label = "high"}) -> i64 {
    %zero = llvm.mlir.constant(0 : i64) : i64
    %a_is_zero = llvm.icmp "eq" %secret_a, %zero : i64
    // PREFLIGHT FINDING: secret-dependent target-helper branch
    // secret source: %a_is_zero is derived from secret %secret_a
    // observable effect: the observer-visible compute host exposes the immediate successor
    // reason: secret_a values zero and one select distinct target-helper blocks
    // preflight expectation: the synthetic oracle selects BranchSuccessor.successor as first bad
    llvm.cond_br %a_is_zero, ^zero_product, ^multiply {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"],
      sps.observable_candidate = ["control"]
    }
  ^zero_product:
    llvm.return %zero : i64
  ^multiply:
    %product = llvm.mul %secret_a, %secret_b : i64
    llvm.return %product : i64
  }
}
