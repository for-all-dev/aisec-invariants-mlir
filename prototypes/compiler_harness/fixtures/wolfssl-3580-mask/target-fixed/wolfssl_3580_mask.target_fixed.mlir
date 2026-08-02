// RUN: %checkpoint-runner run --snapshot fixtures/wolfssl-3580-mask/target-fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wolfssl-3580-mask/target-fixed/wolfssl_3580_mask.target_fixed.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic fixed-mask target model; compiler-conformance evidence separately compares backend output
// artifact status: hand-written fixed target model
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @wolfssl_3580_select_fixed(
      %table_index: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %scan_index: i32,
      %table_value: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i32) : i32
    %thirty_one = llvm.mlir.constant(31 : i32) : i32
    %x = llvm.xor %scan_index, %table_index : i32
    %neg_x = llvm.sub %zero, %x : i32
    %nonzero_bits = llvm.or %x, %neg_x : i32
    %top = llvm.lshr %nonzero_bits, %thirty_one : i32
    %is_zero = llvm.xor %top, %one : i32
    // PREFLIGHT CONTROL: branchless equality mask
    // secret source: %table_index contributes only to mask dataflow
    // safe effect: every scan iteration performs the same control flow and table access pattern
    // reason: equality is converted to a full-word mask instead of selecting a successor
    // preflight expectation: preflight diagnostic accepts this target model when the target profile gives these ops constant timing
    %mask = llvm.sub %zero, %is_zero {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"],
      sps.observable_candidate = ["control", "timing"]
    } : i32
    %selected = llvm.and %table_value, %mask : i32
    llvm.return %selected : i32
  }
}
