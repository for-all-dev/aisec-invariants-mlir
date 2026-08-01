// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.cond_br
//
// scope note: preflight checks the in-module helper shape; separately bound
// backend evidence is required for deployment refinement
// artifact status: hand-written target model; the helper body is included in the verified region
//
// CHECK-LABEL: llvm.func @clangover_ct_cmov_model
// CHECK-SAME: %[[IF_ZERO:[a-zA-Z0-9_]+]]: i16, %[[IF_ONE:[a-zA-Z0-9_]+]]: i16, %[[BIT:[a-zA-Z0-9_]+]]: i16
// CHECK-NOT: llvm.cond_br
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i16) : i16
// CHECK: %[[ALL_ONES:[0-9]+]] = llvm.mlir.constant(-1 : i16) : i16
// CHECK: %[[MASK:[0-9]+]] = llvm.sub %[[ZERO]], %[[BIT]]
// CHECK-NOT: llvm.cond_br
// CHECK: %[[NOT_MASK:[0-9]+]] = llvm.xor %[[MASK]], %[[ALL_ONES]]
// CHECK: %[[LEFT:[0-9]+]] = llvm.and %[[IF_ZERO]], %[[NOT_MASK]]
// CHECK: %[[RIGHT:[0-9]+]] = llvm.and %[[IF_ONE]], %[[MASK]]
// CHECK: %[[SELECTED:[0-9]+]] = llvm.or %[[LEFT]], %[[RIGHT]]
// CHECK-NOT: llvm.cond_br
// CHECK: llvm.return %[[SELECTED]]
// CHECK-LABEL: llvm.func @clangover_poly_frommsg_fixed
// CHECK-SAME: %[[WRAPPER_BIT:[a-zA-Z0-9_]+]]: i16
// CHECK-NOT: llvm.cond_br
// CHECK: %[[WRAPPER_ZERO:[0-9]+]] = llvm.mlir.constant(0 : i16) : i16
// CHECK: %[[CONSTANT:[0-9]+]] = llvm.mlir.constant(1665 : i16) : i16
// CHECK: %[[COEFFICIENT:[0-9]+]] = llvm.call @clangover_ct_cmov_model(%[[WRAPPER_ZERO]], %[[CONSTANT]], %[[WRAPPER_BIT]])
// CHECK-NOT: llvm.cond_br
// CHECK: llvm.return %[[COEFFICIENT]]
module {
  llvm.func @clangover_ct_cmov_model(%if_zero: i16, %if_one: i16, %bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %all_ones = llvm.mlir.constant(-1 : i16) : i16
    // PREFLIGHT CONTROL: mask-based conditional move
    // secret source: %bit is used only to construct a full-word mask
    // safe effect: control flow and memory addresses are independent of %bit
    // reason: both values are combined through dataflow rather than successor selection
    // preflight expectation: unary scanner sees no candidate-secret branch in the modeled helper
    %mask = llvm.sub %zero, %bit : i16
    %not_mask = llvm.xor %mask, %all_ones : i16
    %left = llvm.and %if_zero, %not_mask : i16
    %right = llvm.and %if_one, %mask : i16
    %selected = llvm.or %left, %right : i16
    llvm.return %selected : i16
  }

  llvm.func @clangover_poly_frommsg_fixed(%bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    %coefficient = llvm.call @clangover_ct_cmov_model(%zero, %constant, %bit) : (i16, i16, i16) -> i16
    llvm.return %coefficient : i16
  }
}
