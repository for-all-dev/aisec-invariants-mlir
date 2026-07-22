// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.udiv
//
// case: kyberslash2/poly_compress
// classification: compiler-generated-minimized
// c source: ../c/kyberslash2_compress_fixed.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/commit/11d00ff1f20cfca1f72d819e5a45165c1e0a2816
// upstream revision: 11d00ff1f20cfca1f72d819e5a45165c1e0a2816
// secret: %coefficient
// public: KYBER_Q-derived reciprocal and shift constants
// expected outcome: verified
// observer/model: source-operation-timing
// reason id: variable-latency-op-removed
// outstanding obligations: none
// evidence boundary: L1 source-operation model confirms no division remains
//
// CHECK-LABEL: llvm.func @kyberslash2_compress_fixed
// CHECK-SAME: %[[COEFFICIENT:[a-zA-Z0-9_]+]]: i32
// CHECK-NOT: llvm.udiv
// CHECK: %[[INPUT_SHIFT:[0-9]+]] = llvm.mlir.constant(4 : i32) : i32
// CHECK: %[[ROUND:[0-9]+]] = llvm.mlir.constant(1665 : i32) : i32
// CHECK: %[[RECIPROCAL:[0-9]+]] = llvm.mlir.constant(80635 : i32) : i32
// CHECK: %[[RECIPROCAL_SHIFT:[0-9]+]] = llvm.mlir.constant(28 : i32) : i32
// CHECK: %[[SHIFTED:[0-9]+]] = llvm.shl %[[COEFFICIENT]], %[[INPUT_SHIFT]]
// CHECK: %[[NUMERATOR:[0-9]+]] = llvm.add %[[SHIFTED]], %[[ROUND]]
// CHECK: %[[SCALED:[0-9]+]] = llvm.mul %[[NUMERATOR]], %[[RECIPROCAL]]
// CHECK-NOT: llvm.udiv
// CHECK: %[[QUOTIENT:[0-9]+]] = llvm.lshr %[[SCALED]], %[[RECIPROCAL_SHIFT]]
// CHECK-NOT: llvm.udiv
// CHECK: llvm.return
module {
  llvm.func @kyberslash2_compress_fixed(%coefficient: i32) -> i32 {
    %four = llvm.mlir.constant(4 : i32) : i32
    %fifteen = llvm.mlir.constant(15 : i32) : i32
    %round = llvm.mlir.constant(1665 : i32) : i32
    %reciprocal = llvm.mlir.constant(80635 : i32) : i32
    %shift = llvm.mlir.constant(28 : i32) : i32
    %shifted = llvm.shl %coefficient, %four : i32
    %numerator = llvm.add %shifted, %round : i32
    // CONFIDENTIALITY REPAIR: reciprocal multiply replaces division
    // secret source: %numerator is derived from secret %coefficient
    // safe effect: no division instruction or helper is selected before the public four-bit mask
    // reason: multiply/add/shift sequence preserves the documented compressed value on the Kyber coefficient domain
    // detection boundary: L1 confirms forbidden division is absent
    %scaled = llvm.mul %numerator, %reciprocal : i32
    %quotient = llvm.lshr %scaled, %shift : i32
    %compressed = llvm.and %quotient, %fifteen : i32
    llvm.return %compressed : i32
  }
}
