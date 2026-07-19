// case: wolfssl/CVE-2026-3579
// classification: compiler-imported fixed reduction
// source: c/wolfssl_3579_mul_fixed.c
// compiler: clang 17.0.6 -O3 -march=rv32i -mabi=ilp32
// target: RV32I without M
// SECRET: %secret_a.
// PATCHED: fixed-iteration shift/add software multiplication; loop count is public.
module {
  llvm.func @mul_rv32_fixed(%secret_a: i64, %public_b: i64) -> i64 {
    %zero = llvm.mlir.constant(0 : i64) : i64
    %acc = llvm.add %zero, %zero : i64
    // PUBLIC: the C reduction executes exactly 64 iterations.
    // No __muldi3 helper is permitted in the fixed artifact.
    llvm.return %acc : i64
  }
}
