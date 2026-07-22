// RUN: %mlir-opt %s | %FileCheck %s
//
// case: wolfssl/CVE-2026-3579
// classification: compiler-generated-minimized
// c source: ../c/wolfssl_3579_mul_vulnerable.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
// upstream revision: b6fbfad945d4b98fce619b6e5b6561b3eca1205b
// secret: %secret_a and %secret_b
// public: target profile RV32I without the M extension
// expected outcome: unknown
// observer/model: rv32i-helper-timing
// reason id: missing-target-timing
// outstanding obligations: target-lowering-semantics,helper-latency-contract
// evidence boundary: source llvm.mul at L1 establishes no target timing fact; target evidence is L3/L4
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
