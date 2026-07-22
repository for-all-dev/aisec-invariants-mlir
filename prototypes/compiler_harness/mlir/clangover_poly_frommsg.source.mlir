// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.cond_br
//
// case: clangover/poly_frommsg
// classification: compiler-generated-minimized
// c source: ../c/clangover_poly_frommsg_vulnerable.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L141-L159
// upstream revision: b628ba78711bc28327dc7d2d5c074a00f061884e
// secret: %bit, one bit derived from the message byte
// public: coefficient constant 1665
// expected outcome: verified
// observer/model: source-operation-timing
// reason id: source-branchless-dataflow
// outstanding obligations: none
// evidence boundary: L1 source boundary; the separate lowered model records the L3 regression
//
// CHECK-LABEL: llvm.func @clangover_poly_frommsg_source
// CHECK-SAME: %[[BIT:[a-zA-Z0-9_]+]]: i16
// CHECK-NOT: llvm.cond_br
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i16) : i16
// CHECK: %[[CONSTANT:[0-9]+]] = llvm.mlir.constant(1665 : i16) : i16
// CHECK: %[[MASK:[0-9]+]] = llvm.sub %[[ZERO]], %[[BIT]]
// CHECK-NOT: llvm.cond_br
// CHECK: %[[COEFFICIENT:[0-9]+]] = llvm.and %[[MASK]], %[[CONSTANT]]
// CHECK-NOT: llvm.cond_br
// CHECK: llvm.return %[[COEFFICIENT]]
module {
  llvm.func @clangover_poly_frommsg_source(%bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    %mask = llvm.sub %zero, %bit : i16
    %coefficient = llvm.and %mask, %constant : i16
    llvm.return %coefficient : i16
  }
}
