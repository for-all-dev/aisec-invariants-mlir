/*
 * CVE-2026-3580 fixed-shape reduction.  The equality is computed as a
 * bitwise zero/nonzero test in a noinline helper, so the caller cannot turn
 * the secret index into a conditional load or branch.
 * Upstream fix: https://github.com/wolfSSL/wolfssl/pull/9855
 * Compile: gcc -O3 -march=rv32i -mabi=ilp32 -S (historical target).
 * Secret input: table_index; expected unsafe instruction: bnez/bne.
 * Classification: fixed clean-room reduction.
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
