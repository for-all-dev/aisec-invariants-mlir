/*
 * Case: wolfSSL CVE-2026-3579 RV32I fixed-iteration multiply reduction
 *
 * Upstream repository:
 *   https://github.com/wolfSSL/wolfssl
 *
 * Original vulnerable code:
 *   https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
 *
 * Original fixed code:
 *   https://github.com/wolfSSL/wolfssl/tree/8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5/wolfcrypt/src
 *
 * Upstream symbol:
 *   sp_256_mul_9 and related SP arithmetic
 *
 * Upstream vulnerable revision:
 *   b6fbfad945d4b98fce619b6e5b6561b3eca1205b
 *
 * Upstream fixed revision:
 *   8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5
 *
 * Reduction classification:
 *   independently-written-equivalent-reduction
 *
 * Relationship to upstream:
 *   Replaces the compiler helper with a public 64-iteration shift/mask/add
 *   routine for the same unsigned multiplication result.
 *
 * Secret inputs:
 *   secret_a and secret_b
 *
 * Public inputs:
 *   fixed loop count 64 and target profile
 *
 * Expected confidentiality issue:
 *   The fixed reduction should not call __muldi3 or branch on secret bits.
 *
 * Canonical compiler command:
 *   clang -O3 --target=riscv32-unknown-elf -march=rv32i -mabi=ilp32 -S wolfssl_3579_mul_fixed.c
 *
 * License note:
 *   This independently written reduction contains no copied wolfSSL source.
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
