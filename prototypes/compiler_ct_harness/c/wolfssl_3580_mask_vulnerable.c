/*
 * Case: wolfSSL CVE-2026-3580 table-selection mask vulnerable reduction
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
 *   Re-expresses only the fixed-count table scan and equality-mask selection
 *   shape. It does not copy the GPL-licensed wolfSSL function body.
 *
 * Secret inputs:
 *   table_index
 *
 * Public inputs:
 *   table contents and fixed scan bound 16
 *
 * Expected confidentiality issue:
 *   On RV32I with GCC -O3, the equality mask can be lowered to a
 *   secret-dependent bnez/bne branch.
 *
 * Canonical compiler command:
 *   riscv32-gcc -O3 -march=rv32i -mabi=ilp32 -S wolfssl_3580_mask_vulnerable.c
 *
 * License note:
 *   This independently written reduction contains no copied wolfSSL source.
 */
typedef unsigned int uint32_t;

__attribute__((noinline))
uint32_t wolfssl_3580_mask_vulnerable(const uint32_t table[16],
                                      uint32_t table_index) {
  uint32_t result = 0;
  for (uint32_t i = 0; i < 16; ++i) {
    uint32_t mask = 0u - (uint32_t)(i == table_index);
    result |= table[i] & mask;
  }
  return result;
}
