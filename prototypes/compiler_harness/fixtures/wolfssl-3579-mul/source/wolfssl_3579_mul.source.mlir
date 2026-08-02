// RUN: %checkpoint-runner run --snapshot fixtures/wolfssl-3579-mul/source/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wolfssl-3579-mul/source/wolfssl_3579_mul.source.mlir --records %t.checkpoints

//
// scope note: the source llvm.mul shape establishes no helper-latency fact;
// target timing requires separately bound deployment evidence
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @wolfssl_3579_mul_source(
      %secret_a: i64 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %secret_b: i64 {sps.fixture_refs = ["snapshot.secret[1]"], sps.label = "high"}) -> i64 {
    %product = llvm.mul %secret_a, %secret_b {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["timing"]
    } : i64
    llvm.return %product : i64
  }
}
