/*
 * wolfSSL CVE-2026-3579 clean-room reduction.
 * Upstream: https://nvd.nist.gov/vuln/detail/CVE-2026-3579
 * Fix:      https://github.com/wolfSSL/wolfssl/pull/9855
 * Historical target: RV32I without the M extension.
 * Secret: either 64-bit operand.  The ordinary multiply is lowered to
 * compiler helper __muldi3, whose implementation is not operand-independent.
 * Compile: clang -O3 --target=riscv32-unknown-elf -march=rv32i -mabi=ilp32.
 * Expected unsafe instruction: call `__muldi3`.
 * Classification: vulnerable backend-reproduction reduction.
 */
typedef unsigned long long uint64_t;

__attribute__((noinline))
uint64_t wolfssl_3579_mul_vulnerable(uint64_t secret_a, uint64_t secret_b) {
  return secret_a * secret_b;
}
