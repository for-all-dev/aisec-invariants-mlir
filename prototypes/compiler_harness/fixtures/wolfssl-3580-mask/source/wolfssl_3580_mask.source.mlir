// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.cond_br
//
// scope note: preflight diagnostic source-operation model; the separate target model records backend evidence
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @wolfssl_3580_select_source
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[SCAN:[a-zA-Z0-9_]+]]: i32, %[[VALUE:[a-zA-Z0-9_]+]]: i32
// CHECK-NOT: llvm.cond_br
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[EQUAL:[0-9]+]] = llvm.icmp "eq" %[[SCAN]], %[[SECRET]] {sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"], sps.observable_candidate = ["control", "timing"]} : i32
// CHECK: %[[EQUAL32:[0-9]+]] = llvm.zext %[[EQUAL]] : i1 to i32
// CHECK: %[[MASK:[0-9]+]] = llvm.sub %[[ZERO]], %[[EQUAL32]]
// CHECK-NOT: llvm.cond_br
// CHECK: %[[SELECTED:[0-9]+]] = llvm.and %[[VALUE]], %[[MASK]]
// CHECK-NOT: llvm.cond_br
// CHECK: llvm.return %[[SELECTED]]
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
