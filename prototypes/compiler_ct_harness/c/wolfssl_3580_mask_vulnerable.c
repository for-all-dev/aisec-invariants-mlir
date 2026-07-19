/*
 * wolfSSL CVE-2026-3580 clean-room reduction.
 * Upstream: https://osv.dev/vulnerability/CVE-2026-3580
 * Fix:      https://github.com/wolfSSL/wolfssl/pull/9855
 * Historical target: GCC -O3, RISC-V RV32I, symbol sp_256_get_entry_256_9.
 * Secret: table_index.  The scan bound and table contents are public.
 * Compile: gcc -O3 -march=rv32i -mabi=ilp32 -S (historical target).
 * Expected unsafe instruction: secret-dependent `bnez`/`bne`.
 * Classification: modeled backend-reproduction reduction.
 *
 * The intended source idiom is a fixed scan plus an equality mask.  The
 * reported GCC backend can turn the equality into a secret-dependent `bnez`.
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
