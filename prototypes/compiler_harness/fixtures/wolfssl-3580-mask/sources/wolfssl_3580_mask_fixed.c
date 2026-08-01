/*
 * Case: wolfSSL CVE-2026-3580 table-selection mask fixed reduction
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
 *   sp_256_get_entry_256_9
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
 *   Re-expresses only the fixed-count table scan with a branchless equality
 *   mask helper, not the complete wolfSSL ECC routine.
 *
 * Secret inputs:
 *   table_index
 *
 * Public inputs:
 *   table contents and fixed scan bound 16
 *
 * Expected confidentiality issue:
 *   The fixed reduction should not expose table_index through a branch or
 *   conditional table access.
 *
 * Canonical compiler command:
 *   riscv32-gcc -O3 -march=rv32i -mabi=ilp32 -S wolfssl_3580_mask_fixed.c
 *
 * License note:
 *   This independently written reduction contains no copied wolfSSL source.
 */
typedef unsigned int uint32_t;

__attribute__((noinline))
static uint32_t ct_eq_mask(uint32_t a, uint32_t b) {
  uint32_t x = a ^ b;
  x |= 0u - x;
  return 0u - ((x >> 31) ^ 1u);
}

__attribute__((noinline))
uint32_t wolfssl_3580_mask_fixed(const uint32_t table[16],
                                 uint32_t table_index) {
  uint32_t result = 0;
  for (uint32_t i = 0; i < 16; ++i)
    result |= table[i] & ct_eq_mask(i, table_index);
  return result;
}
