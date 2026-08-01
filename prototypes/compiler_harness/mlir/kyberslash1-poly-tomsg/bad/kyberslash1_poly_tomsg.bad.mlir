// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: direct preflight diagnostic variable-time division check
//
// CHECK-LABEL: llvm.func @kyberslash1_poly_tomsg_bad
// CHECK-SAME: %[[COEFFICIENT:[a-zA-Z0-9_]+]]: i32 {sps.label = "high"}
// CHECK: %[[ONE:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[ROUND:[0-9]+]] = llvm.mlir.constant(1664 : i32) : i32
// CHECK: %[[DIVISOR:[0-9]+]] = llvm.mlir.constant(3329 : i32) : i32
// CHECK: %[[SHIFTED:[0-9]+]] = llvm.shl %[[COEFFICIENT]], %[[ONE]]
// CHECK: %[[NUMERATOR:[0-9]+]] = llvm.add %[[SHIFTED]], %[[ROUND]]
// CHECK: %[[QUOTIENT:[0-9]+]] = llvm.udiv %[[NUMERATOR]], %[[DIVISOR]]
module {
  llvm.func @kyberslash1_poly_tomsg_bad(%coefficient: i32 {sps.label = "high"}) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %round = llvm.mlir.constant(1664 : i32) : i32
    %q = llvm.mlir.constant(3329 : i32) : i32
    %shifted = llvm.shl %coefficient, %one : i32
    %numerator = llvm.add %shifted, %round : i32
    // PREFLIGHT FINDING: secret-dependent division
    // secret source: %numerator is derived from secret %coefficient
    // observable effect: division latency can vary with the numerator value
    // reason: inputs differing only in %coefficient execute a variable-time llvm.udiv
    // preflight expectation: direct preflight diagnostic source/LLVM-dialect check
    %quotient = llvm.udiv %numerator, %q : i32
    %bit = llvm.and %quotient, %one : i32
    llvm.return %bit : i32
  }
}
