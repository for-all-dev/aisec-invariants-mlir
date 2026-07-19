/*
 * Patched Clangover reduction.
 * Provenance and rationale: see clangover_ct_cmov.c and the Clangover links
 * in clangover_poly_frommsg_vulnerable.c.  No LTO is used for this pair.
 * Compile: clang -Os -fno-vectorize -fno-slp-vectorize -S (no LTO).
 * Secret input: msg; expected unsafe instruction: secret-dependent jcc.
 * Classification: fixed regression reduction.
 */
typedef unsigned char uint8_t;
typedef signed short int16_t;
typedef unsigned short uint16_t;

extern int16_t clangover_ct_cmov(int16_t if_zero, int16_t if_one,
                                 uint16_t bit);

__attribute__((noinline))
void clangover_poly_frommsg_fixed(int16_t out[256], const uint8_t msg[32]) {
  for (unsigned i = 0; i < 32; ++i) {
    for (unsigned j = 0; j < 8; ++j) {
      uint16_t bit = (uint16_t)((msg[i] >> j) & 1u);
      out[8 * i + j] = clangover_ct_cmov(0, 1665, bit);
    }
  }
}
