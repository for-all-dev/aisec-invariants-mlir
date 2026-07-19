/*
 * Separate translation-unit helper used by the patched Clangover reduction.
 * Keeping the binary condition out of the caller prevents the optimizer from
 * folding the mask into a branch when the files are compiled without LTO.
 * Provenance: https://github.com/antoonpurnal/clangover (patched strategy).
 * Compile: clang -Os -fno-vectorize -fno-slp-vectorize -c (no LTO).
 * Secret input: bit; expected unsafe instruction: secret-dependent jcc.
 * Classification: fixed helper reduction.
 */
typedef unsigned short uint16_t;
typedef signed short int16_t;

__attribute__((noinline))
int16_t clangover_ct_cmov(int16_t if_zero, int16_t if_one, uint16_t bit) {
  uint16_t mask = (uint16_t)(0u - bit);
  uint16_t a = (uint16_t)if_zero;
  uint16_t b = (uint16_t)if_one;
  return (int16_t)((a & (uint16_t)~mask) | (b & mask));
}
