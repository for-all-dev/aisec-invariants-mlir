// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: direct preflight diagnostic variable-time division check
//
// CHECK-LABEL: llvm.func @kyberslash2_compress_bad
// CHECK-SAME: %[[COEFFICIENT:[a-zA-Z0-9_]+]]: i32
// CHECK: %[[SHIFT:[0-9]+]] = llvm.mlir.constant(4 : i32) : i32
// CHECK: %[[ROUND:[0-9]+]] = llvm.mlir.constant(1664 : i32) : i32
// CHECK: %[[DIVISOR:[0-9]+]] = llvm.mlir.constant(3329 : i32) : i32
// CHECK: %[[SHIFTED:[0-9]+]] = llvm.shl %[[COEFFICIENT]], %[[SHIFT]]
// CHECK: %[[NUMERATOR:[0-9]+]] = llvm.add %[[SHIFTED]], %[[ROUND]]
// CHECK: %[[QUOTIENT:[0-9]+]] = llvm.udiv %[[NUMERATOR]], %[[DIVISOR]]
module {
  llvm.func @kyberslash2_compress_bad(%coefficient: i32) -> i32 {
    %four = llvm.mlir.constant(4 : i32) : i32
    %fifteen = llvm.mlir.constant(15 : i32) : i32
    %round = llvm.mlir.constant(1664 : i32) : i32
    %q = llvm.mlir.constant(3329 : i32) : i32
    %shifted = llvm.shl %coefficient, %four : i32
    %numerator = llvm.add %shifted, %round : i32
    // PREFLIGHT FINDING: secret-dependent division
    // secret source: %numerator is derived from secret %coefficient
    // observable effect: division latency can vary with the numerator value
    // reason: inputs differing only in %coefficient execute a variable-time llvm.udiv before the public four-bit mask
    // preflight expectation: direct preflight diagnostic source/LLVM-dialect check
    %quotient = llvm.udiv %numerator, %q : i32
    %compressed = llvm.and %quotient, %fifteen : i32
    llvm.return %compressed : i32
  }
}
