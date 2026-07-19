// case: wolfssl/CVE-2026-3579
// classification: compiler-imported source operation
// source: c/wolfssl_3579_mul_vulnerable.c
// compiler: clang 17.0.6 -O3 -march=rv32i -mabi=ilp32
// target: RV32I
// SECRET: %secret_a participates in a 64-bit multiplication.
module {
  llvm.func @mul_source(%secret_a: i64, %public_b: i64) -> i64 {
    %product = llvm.mul %secret_a, %public_b : i64
    llvm.return %product : i64
  }
}
