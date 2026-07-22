// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not='llvm.call @__muldi3' --implicit-check-not=llvm.cond_br
// RUN: %mlir-opt %s | %FileCheck %s --check-prefix=COUNT --implicit-check-not='llvm.call @__muldi3' --implicit-check-not=llvm.cond_br
//
// case: wolfssl/CVE-2026-3579
// classification: modeled-fixed-target
// c source: ../c/wolfssl_3579_mul_fixed.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/tree/8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5/wolfcrypt/src
// upstream revision: 8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5
// secret: %secret_a and %secret_b
// public: fixed loop count 64 and selected fixed-operation RV32I profile
// expected outcome: conditional
// observer/model: modeled-rv32i-timing
// reason id: fixed-loop-requires-target-evidence
// outstanding obligations: base-operation-latency,backend-trace-preservation
// evidence boundary: L1 verifies the fixed loop; target-operation and backend-conformance facts remain L4
// artifact status: hand-written fixed target model
//
// CHECK-LABEL: llvm.func @wolfssl_3579_mul_fixed_model
// CHECK-SAME: %[[SECRET_A:[a-zA-Z0-9_]+]]: i64, %[[SECRET_B:[a-zA-Z0-9_]+]]: i64
// CHECK: %[[ZERO64:[0-9]+]] = llvm.mlir.constant(0 : i64) : i64
// CHECK: %[[ONE64:[0-9]+]] = llvm.mlir.constant(1 : i64) : i64
// CHECK: %[[ZERO32:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[ONE32:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[BOUND:[0-9]+]] = llvm.mlir.constant(64 : i32) : i32
// CHECK-NOT: llvm.call @__muldi3
// CHECK: llvm.br ^bb1(%[[ZERO32]], %[[ZERO64]], %[[SECRET_A]], %[[SECRET_B]] : i32, i64, i64, i64)
// CHECK: ^bb1(%[[INDEX:[0-9]+]]: i32, %[[ACC:[0-9]+]]: i64, %[[ADDEND:[0-9]+]]: i64, %[[MULT:[0-9]+]]: i64)
// CHECK: %[[DONE:[0-9]+]] = llvm.icmp "eq" %[[INDEX]], %[[BOUND]] : i32
// CHECK-NOT: llvm.call @__muldi3
// CHECK: llvm.cond_br %[[DONE]],
// CHECK-NOT: llvm.call @__muldi3
// CHECK: %[[LOW_BIT:[0-9]+]] = llvm.and %[[MULT]], %[[ONE64]]
// CHECK: %[[NEXT_INDEX:[0-9]+]] = llvm.add %[[INDEX]], %[[ONE32]]
// CHECK: llvm.br ^bb1(%[[NEXT_INDEX]],
// CHECK-NOT: llvm.call @__muldi3
// CHECK: llvm.return
//
// COUNT-COUNT-1: llvm.cond_br
module {
  llvm.func @wolfssl_3579_mul_fixed_model(%secret_a: i64, %secret_b: i64) -> i64 {
    %zero64 = llvm.mlir.constant(0 : i64) : i64
    %one64 = llvm.mlir.constant(1 : i64) : i64
    %zero32 = llvm.mlir.constant(0 : i32) : i32
    %one32 = llvm.mlir.constant(1 : i32) : i32
    %sixty_four = llvm.mlir.constant(64 : i32) : i32
    llvm.br ^loop(%zero32, %zero64, %secret_a, %secret_b : i32, i64, i64, i64)
  ^loop(%i: i32, %acc: i64, %addend: i64, %mult: i64):
    %done = llvm.icmp "eq" %i, %sixty_four : i32
    llvm.cond_br %done, ^exit(%acc : i64), ^body
  ^body:
    %low_bit = llvm.and %mult, %one64 : i64
    // CONFIDENTIALITY REPAIR: fixed-iteration mask/add multiplication
    // secret source: %low_bit is a secret bit of %secret_b
    // safe effect: it affects only a mask operand, not loop count, branch direction, address, or helper selection
    // reason: all 64 iterations execute for every input and no __muldi3 call is emitted
    // detection boundary: L1 accepts this shape with a constant-time RV32I operation profile
    %mask = llvm.sub %zero64, %low_bit : i64
    %masked_addend = llvm.and %addend, %mask : i64
    %acc_next = llvm.add %acc, %masked_addend : i64
    %addend_next = llvm.shl %addend, %one64 : i64
    %mult_next = llvm.lshr %mult, %one64 : i64
    %i_next = llvm.add %i, %one32 : i32
    llvm.br ^loop(%i_next, %acc_next, %addend_next, %mult_next : i32, i64, i64, i64)
  ^exit(%result: i64):
    llvm.return %result : i64
  }
}
