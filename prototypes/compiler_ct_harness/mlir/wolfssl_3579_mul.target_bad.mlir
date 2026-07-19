// case: wolfssl/CVE-2026-3579
// classification: modeled-from-verified-RV32I-assembly
// source: c/wolfssl_3579_mul_vulnerable.c
// compiler: clang 17.0.6 -O3 -march=rv32i -mabi=ilp32
// target: RV32I without M
// SECRET: %secret_a.
// CONFIDENTIALITY BREAK: backend legalization emits variable-time __muldi3.
module {
  llvm.func @mul_rv32_bad_model(%secret_a: i64, %public_b: i64) -> i64 {
    // LLVM dialect before legalization: llvm.mul i64.
    // Verified assembly: call __muldi3@plt.
    // CONFIDENTIALITY BREAK: the helper's running time depends on operands.
    %product = llvm.call @__muldi3(%secret_a, %public_b) : (i64, i64) -> i64
    llvm.return %product : i64
  }
  llvm.func @__muldi3(%a: i64, %b: i64) -> i64
}
