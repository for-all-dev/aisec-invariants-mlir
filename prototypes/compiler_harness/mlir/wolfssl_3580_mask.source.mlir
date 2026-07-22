// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.cond_br
//
// case: wolfssl/CVE-2026-3580
// classification: compiler-generated-minimized
// c source: ../c/wolfssl_3580_mask_vulnerable.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
// upstream revision: b6fbfad945d4b98fce619b6e5b6561b3eca1205b
// secret: %table_index
// public: %scan_index, %table_value, and fixed scan bound
// expected outcome: verified
// observer/model: source-operation-timing
// reason id: source-branchless-dataflow
// outstanding obligations: none
// evidence boundary: L1 source-operation model; the separate target model records L3 backend evidence
//
// CHECK-LABEL: llvm.func @wolfssl_3580_select_source
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32, %[[SCAN:[a-zA-Z0-9_]+]]: i32, %[[VALUE:[a-zA-Z0-9_]+]]: i32
// CHECK-NOT: llvm.cond_br
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[EQUAL:[0-9]+]] = llvm.icmp "eq" %[[SCAN]], %[[SECRET]] : i32
// CHECK: %[[EQUAL32:[0-9]+]] = llvm.zext %[[EQUAL]] : i1 to i32
// CHECK: %[[MASK:[0-9]+]] = llvm.sub %[[ZERO]], %[[EQUAL32]]
// CHECK-NOT: llvm.cond_br
// CHECK: %[[SELECTED:[0-9]+]] = llvm.and %[[VALUE]], %[[MASK]]
// CHECK-NOT: llvm.cond_br
// CHECK: llvm.return %[[SELECTED]]
module {
  llvm.func @wolfssl_3580_select_source(%table_index: i32, %scan_index: i32, %table_value: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %eq = llvm.icmp "eq" %scan_index, %table_index : i32
    %eq32 = llvm.zext %eq : i1 to i32
    %mask = llvm.sub %zero, %eq32 : i32
    %selected = llvm.and %table_value, %mask : i32
    llvm.return %selected : i32
  }
}
