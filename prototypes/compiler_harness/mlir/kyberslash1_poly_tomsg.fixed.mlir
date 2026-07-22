// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.udiv
//
// case: kyberslash1/poly_tomsg
// classification: compiler-generated-minimized
// c source: ../c/kyberslash1_poly_tomsg_fixed.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/commit/dda29cc63af721981ee2c831cf00822e69be3220
// upstream revision: dda29cc63af721981ee2c831cf00822e69be3220
// secret: %coefficient
// public: KYBER_Q-derived reciprocal and shift constants
// expected outcome: verified
// observer/model: source-operation-timing
// reason id: variable-latency-op-removed
// outstanding obligations: none
// evidence boundary: L1 source-operation model confirms no division remains
//
// CHECK-LABEL: llvm.func @kyberslash1_poly_tomsg_fixed
// CHECK-SAME: %[[COEFFICIENT:[a-zA-Z0-9_]+]]: i32
// CHECK-NOT: llvm.udiv
// CHECK: %[[ONE:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[ROUND:[0-9]+]] = llvm.mlir.constant(1665 : i32) : i32
// CHECK: %[[RECIPROCAL:[0-9]+]] = llvm.mlir.constant(80635 : i32) : i32
// CHECK: %[[SHIFT:[0-9]+]] = llvm.mlir.constant(28 : i32) : i32
// CHECK: %[[SHIFTED:[0-9]+]] = llvm.shl %[[COEFFICIENT]], %[[ONE]]
// CHECK: %[[NUMERATOR:[0-9]+]] = llvm.add %[[SHIFTED]], %[[ROUND]]
// CHECK: %[[SCALED:[0-9]+]] = llvm.mul %[[NUMERATOR]], %[[RECIPROCAL]]
// CHECK-NOT: llvm.udiv
// CHECK: %[[QUOTIENT:[0-9]+]] = llvm.lshr %[[SCALED]], %[[SHIFT]]
// CHECK-NOT: llvm.udiv
// CHECK: llvm.return
module {
  llvm.func @kyberslash1_poly_tomsg_fixed(%coefficient: i32) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %round = llvm.mlir.constant(1665 : i32) : i32
    %reciprocal = llvm.mlir.constant(80635 : i32) : i32
    %shift = llvm.mlir.constant(28 : i32) : i32
    %shifted = llvm.shl %coefficient, %one : i32
    %numerator = llvm.add %shifted, %round : i32
    // CONFIDENTIALITY REPAIR: reciprocal multiply replaces division
    // secret source: %numerator is derived from secret %coefficient
    // safe effect: no division instruction or helper is selected
    // reason: multiply/add/shift sequence preserves the documented bit result on the Kyber coefficient domain
    // detection boundary: L1 confirms forbidden division is absent
    %scaled = llvm.mul %numerator, %reciprocal : i32
    %quotient = llvm.lshr %scaled, %shift : i32
    %bit = llvm.and %quotient, %one : i32
    llvm.return %bit : i32
  }
}
