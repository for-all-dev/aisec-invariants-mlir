// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.cond_br
//
// scope note: preflight diagnostic source boundary; the separate lowered model records the compiler-introduced regression
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @clangover_poly_frommsg_source
// CHECK-SAME: %[[BIT:[a-zA-Z0-9_]+]]: i16 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}
// CHECK-NOT: llvm.cond_br
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i16) : i16
// CHECK: %[[CONSTANT:[0-9]+]] = llvm.mlir.constant(1665 : i16) : i16
// CHECK: %[[MASK:[0-9]+]] = llvm.sub %[[ZERO]], %[[BIT]] {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["timing"]}
// CHECK-NOT: llvm.cond_br
// CHECK: %[[COEFFICIENT:[0-9]+]] = llvm.and %[[MASK]], %[[CONSTANT]]
// CHECK-NOT: llvm.cond_br
// CHECK: llvm.return %[[COEFFICIENT]]
module {
  llvm.func @clangover_poly_frommsg_source(
      %bit: i16 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    %mask = llvm.sub %zero, %bit {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["timing"]
    } : i16
    %coefficient = llvm.and %mask, %constant : i16
    llvm.return %coefficient : i16
  }
}
