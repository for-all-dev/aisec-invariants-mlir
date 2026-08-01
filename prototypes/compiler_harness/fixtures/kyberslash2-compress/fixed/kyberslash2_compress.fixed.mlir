// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.udiv
//
// scope note: preflight diagnostic source-operation model confirms no division remains
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @kyberslash2_compress_fixed
// CHECK-SAME: %[[COEFFICIENT:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}
// CHECK-NOT: llvm.udiv
// CHECK: %[[INPUT_SHIFT:[0-9]+]] = llvm.mlir.constant(4 : i32) : i32
// CHECK: %[[ROUND:[0-9]+]] = llvm.mlir.constant(1665 : i32) : i32
// CHECK: %[[RECIPROCAL:[0-9]+]] = llvm.mlir.constant(80635 : i32) : i32
// CHECK: %[[RECIPROCAL_SHIFT:[0-9]+]] = llvm.mlir.constant(28 : i32) : i32
// CHECK: %[[SHIFTED:[0-9]+]] = llvm.shl %[[COEFFICIENT]], %[[INPUT_SHIFT]]
// CHECK: %[[NUMERATOR:[0-9]+]] = llvm.add %[[SHIFTED]], %[[ROUND]]
// CHECK: %[[SCALED:[0-9]+]] = llvm.mul %[[NUMERATOR]], %[[RECIPROCAL]] {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["timing"]}
// CHECK-NOT: llvm.udiv
// CHECK: %[[QUOTIENT:[0-9]+]] = llvm.lshr %[[SCALED]], %[[RECIPROCAL_SHIFT]]
// CHECK-NOT: llvm.udiv
// CHECK: llvm.return
module {
  llvm.func @kyberslash2_compress_fixed(
      %coefficient: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i32 {
    %four = llvm.mlir.constant(4 : i32) : i32
    %fifteen = llvm.mlir.constant(15 : i32) : i32
    %round = llvm.mlir.constant(1665 : i32) : i32
    %reciprocal = llvm.mlir.constant(80635 : i32) : i32
    %shift = llvm.mlir.constant(28 : i32) : i32
    %shifted = llvm.shl %coefficient, %four : i32
    %numerator = llvm.add %shifted, %round : i32
    // PREFLIGHT CONTROL: reciprocal multiply replaces division
    // secret source: %numerator is derived from secret %coefficient
    // safe effect: no division instruction or helper is selected before the public four-bit mask
    // reason: multiply/add/shift sequence preserves the documented compressed value on the Kyber coefficient domain
    // preflight expectation: preflight diagnostic confirms forbidden division is absent
    %scaled = llvm.mul %numerator, %reciprocal {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["timing"]
    } : i32
    %quotient = llvm.lshr %scaled, %shift : i32
    %compressed = llvm.and %quotient, %fifteen : i32
    llvm.return %compressed : i32
  }
}
