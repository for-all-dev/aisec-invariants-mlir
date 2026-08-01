// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: the source llvm.mul shape establishes no helper-latency fact;
// target timing requires separately bound deployment evidence
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @wolfssl_3579_mul_source
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i64 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[B:[a-zA-Z0-9_]+]]: i64 {sps.fixture_refs = ["snapshot.secret[1]"], sps.label = "high"}
// CHECK: %[[PRODUCT:[0-9]+]] = llvm.mul %[[A]], %[[B]] {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["timing"]} : i64
// CHECK: llvm.return %[[PRODUCT]] : i64
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
