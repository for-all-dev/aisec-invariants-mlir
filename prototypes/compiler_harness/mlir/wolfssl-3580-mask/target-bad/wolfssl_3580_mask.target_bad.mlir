// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: target-model shape plus backend evidence; literal GCC MLIR is not claimed
// artifact status: hand-written target model derived from reported assembly
//
// CHECK-LABEL: llvm.func @wolfssl_3580_rv32_bad_model
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32, %[[SCAN:[a-zA-Z0-9_]+]]: i32, %[[VALUE:[a-zA-Z0-9_]+]]: i32
// CHECK: %[[EQ:[0-9]+]] = llvm.icmp "eq" %[[SCAN]], %[[SECRET]] : i32
// CHECK: llvm.cond_br %[[EQ]],
module {
  // Reported RV32I shape:
  //   xor a?, scan_index, table_index
  //   bnez a?, .Lskip
  llvm.func @wolfssl_3580_rv32_bad_model(%table_index: i32, %scan_index: i32, %table_value: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %eq = llvm.icmp "eq" %scan_index, %table_index : i32
    // PREFLIGHT FINDING: secret-dependent branch
    // secret source: %eq depends on secret %table_index
    // observable effect: RV32I bnez/bne direction and timing expose equality with the public scan index
    // reason: two secret indices select different successors for the same public scan iteration
    // preflight expectation: unary scanner flags the candidate-secret branch in this target model
    llvm.cond_br %eq, ^load, ^skip
  ^load:
    llvm.return %table_value : i32
  ^skip:
    llvm.return %zero : i32
  }
}
