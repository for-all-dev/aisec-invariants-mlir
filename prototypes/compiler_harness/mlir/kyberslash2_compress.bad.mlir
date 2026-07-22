// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: kyberslash2/poly_compress
// classification: compiler-generated-minimized
// c source: ../c/kyberslash2_compress_vulnerable.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L23-L32
// upstream revision: b628ba78711bc28327dc7d2d5c074a00f061884e
// secret: %coefficient
// public: KYBER_Q=3329 and rounding constants
// expected outcome: unsafe
// observer/model: source-operation-timing
// reason id: secret-dependent-variable-latency-op
// outstanding obligations: none
// evidence boundary: direct L1 variable-time division check
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
    // CONFIDENTIALITY ERROR: secret-dependent division
    // secret source: %numerator is derived from secret %coefficient
    // observable effect: division latency can vary with the numerator value
    // reason: inputs differing only in %coefficient execute a variable-time llvm.udiv before the public four-bit mask
    // detection boundary: direct L1 source/LLVM-dialect check
    // expected-error @+1 {{secret-dependent-variable-latency-op}}
    %quotient = llvm.udiv %numerator, %q : i32
    %compressed = llvm.and %quotient, %fifteen : i32
    llvm.return %compressed : i32
  }
}
