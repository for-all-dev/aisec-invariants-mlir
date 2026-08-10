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
      %table: !llvm.ptr {sps.abi_root_ref = "table", sps.label = "public"},
      %table_index: i32 {
        sps.component_ref = "table-index",
        sps.fixture_refs = ["snapshot.secret[0]"],
        sps.label = "high"}) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %eq = llvm.icmp "eq" %table_index, %zero : i32
    // PREFLIGHT FINDING: secret-dependent branch
    // secret source: %eq depends on secret %table_index
    // observable effect: the observer-visible compute host exposes the immediate successor
    // reason: indices zero and one select different successors at public scan position zero
    // preflight expectation: the target-control oracle selects BranchSuccessor.successor as first bad
    llvm.cond_br %eq, ^load, ^skip {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["control"]
    }
  ^load:
    %table_value = llvm.load %table : !llvm.ptr -> i32
    llvm.return %table_value : i32
  ^skip:
    llvm.return %zero : i32
  }
}
