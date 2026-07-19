/*
 * Fixed-iteration software multiplication reduction for RV32I.
 * It has no 64-bit multiply operation and therefore does not require
 * compiler-generated __muldi3.  The loop count is public and fixed at 64.
 * Provenance: https://nvd.nist.gov/vuln/detail/CVE-2026-3579
 * Compile: clang -O3 --target=riscv32-unknown-elf -march=rv32i -mabi=ilp32.
 * Secret input: secret_a; expected unsafe operation: call __muldi3.
 * Classification: fixed clean-room reduction.
 */
typedef unsigned long long uint64_t;

__attribute__((noinline))
uint64_t wolfssl_3579_mul_fixed(uint64_t secret_a, uint64_t secret_b) {
  uint64_t result = 0;
  uint64_t addend = secret_a;
  for (unsigned i = 0; i < 64; ++i) {
    uint64_t mask = 0ull - (secret_b & 1ull);
    result += addend & mask;
    addend <<= 1;
    secret_b >>= 1;
  }
  return result;
}
