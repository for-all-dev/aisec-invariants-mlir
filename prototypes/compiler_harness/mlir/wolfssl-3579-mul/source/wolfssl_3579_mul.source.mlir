// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: the source llvm.mul shape establishes no helper-latency fact;
// target timing requires separately bound deployment evidence
//
// CHECK-LABEL: llvm.func @wolfssl_3579_mul_source
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i64, %[[B:[a-zA-Z0-9_]+]]: i64
// CHECK: %[[PRODUCT:[0-9]+]] = llvm.mul %[[A]], %[[B]] : i64
// CHECK: llvm.return %[[PRODUCT]] : i64
module {
  llvm.func @wolfssl_3579_mul_source(%secret_a: i64, %secret_b: i64) -> i64 {
    %product = llvm.mul %secret_a, %secret_b : i64
    llvm.return %product : i64
  }
}
