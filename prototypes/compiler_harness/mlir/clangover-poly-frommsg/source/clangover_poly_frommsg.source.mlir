// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.cond_br
//
// scope note: preflight diagnostic source boundary; the separate lowered model records the compiler-introduced regression
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
