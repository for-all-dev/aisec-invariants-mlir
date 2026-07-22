// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.cond_br
//
// case: wolfssl/CVE-2026-3580
// classification: modeled-fixed-target
// c source: ../c/wolfssl_3580_mask_fixed.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/tree/8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5/wolfcrypt/src
// upstream revision: 8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5
// secret: %table_index
// public: %scan_index, %table_value, and fixed scan bound
// expected outcome: verified
// observer/model: modeled-rv32i-control-flow-timing
// reason id: branchless-selection
// outstanding obligations: none
// evidence boundary: L1 fixed-mask target model; L3 separately compares backend output
// artifact status: hand-written fixed target model
//
// CHECK-LABEL: llvm.func @wolfssl_3580_select_fixed
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32, %[[SCAN:[a-zA-Z0-9_]+]]: i32, %[[VALUE:[a-zA-Z0-9_]+]]: i32
// CHECK-NOT: llvm.cond_br
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[ONE:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[SHIFT:[0-9]+]] = llvm.mlir.constant(31 : i32) : i32
// CHECK: %[[DIFF:[0-9]+]] = llvm.xor %[[SCAN]], %[[SECRET]]
// CHECK: %[[NEGATED:[0-9]+]] = llvm.sub %[[ZERO]], %[[DIFF]]
// CHECK: %[[EITHER:[0-9]+]] = llvm.or %[[DIFF]], %[[NEGATED]]
// CHECK: %[[TOP:[0-9]+]] = llvm.lshr %[[EITHER]], %[[SHIFT]]
// CHECK-NOT: llvm.cond_br
// CHECK: %[[IS_ZERO:[0-9]+]] = llvm.xor %[[TOP]], %[[ONE]]
// CHECK: %[[MASK:[0-9]+]] = llvm.sub %[[ZERO]], %[[IS_ZERO]]
// CHECK: %[[SELECTED:[0-9]+]] = llvm.and %[[VALUE]], %[[MASK]]
// CHECK-NOT: llvm.cond_br
// CHECK: llvm.return %[[SELECTED]]
module {
  llvm.func @wolfssl_3580_select_fixed(%table_index: i32, %scan_index: i32, %table_value: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i32) : i32
    %thirty_one = llvm.mlir.constant(31 : i32) : i32
    %x = llvm.xor %scan_index, %table_index : i32
    %neg_x = llvm.sub %zero, %x : i32
    %nonzero_bits = llvm.or %x, %neg_x : i32
    %top = llvm.lshr %nonzero_bits, %thirty_one : i32
    %is_zero = llvm.xor %top, %one : i32
    // CONFIDENTIALITY REPAIR: branchless equality mask
    // secret source: %table_index contributes only to mask dataflow
    // safe effect: every scan iteration performs the same control flow and table access pattern
    // reason: equality is converted to a full-word mask instead of selecting a successor
    // detection boundary: L1 accepts this target model when the target profile gives these ops constant timing
    %mask = llvm.sub %zero, %is_zero : i32
    %selected = llvm.and %table_value, %mask : i32
    llvm.return %selected : i32
  }
}
