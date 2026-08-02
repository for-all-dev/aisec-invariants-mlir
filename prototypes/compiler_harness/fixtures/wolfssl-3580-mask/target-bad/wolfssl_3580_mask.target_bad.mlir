// RUN: %checkpoint-runner run --snapshot fixtures/wolfssl-3580-mask/target-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wolfssl-3580-mask/target-bad/wolfssl_3580_mask.target_bad.mlir --records %t.checkpoints

//
// scope note: target-model shape plus backend evidence; literal GCC MLIR is not claimed
// artifact status: hand-written target model derived from reported assembly
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  // Reported RV32I shape:
  //   xor a?, scan_index, table_index
  //   bnez a?, .Lskip
  llvm.func @wolfssl_3580_rv32_bad_model(
      %table_index: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %scan_index: i32,
      %table_value: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %eq = llvm.icmp "eq" %scan_index, %table_index : i32
    // PREFLIGHT FINDING: secret-dependent branch
    // secret source: %eq depends on secret %table_index
    // observable effect: RV32I bnez/bne direction and timing expose equality with the public scan index
    // reason: two secret indices select different successors for the same public scan iteration
    // preflight expectation: unary scanner flags the candidate-secret branch in this target model
    llvm.cond_br %eq, ^load, ^skip {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"],
      sps.observable_candidate = ["control", "timing"]
    }
  ^load:
    llvm.return %table_value : i32
  ^skip:
    llvm.return %zero : i32
  }
}
