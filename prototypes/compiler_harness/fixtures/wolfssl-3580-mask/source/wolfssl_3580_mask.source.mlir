// RUN: %checkpoint-runner run --snapshot fixtures/wolfssl-3580-mask/source/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wolfssl-3580-mask/source/wolfssl_3580_mask.source.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic source-operation model; the separate target model records backend evidence
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @wolfssl_3580_select_source(
      %table_index: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %scan_index: i32,
      %table_value: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %eq = llvm.icmp "eq" %scan_index, %table_index {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"],
      sps.observable_candidate = ["control", "timing"]
    } : i32
    %eq32 = llvm.zext %eq : i1 to i32
    %mask = llvm.sub %zero, %eq32 : i32
    %selected = llvm.and %table_value, %mask : i32
    llvm.return %selected : i32
  }
}
