/*
 * Case: Clangover / separate constant-time conditional-move helper
 *
 * Upstream repository:
 *   https://github.com/antoonpurnal/clangover
 *
 * Original vulnerable code:
 *   https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L141-L159
 *
 * Original fixed code:
 *   https://github.com/antoonpurnal/clangover/tree/7f4d5dc162b77c362a34a0d52949f7a3e1b16d81
 *
 * Upstream symbol:
 *   poly_frommsg mitigation helper
 *
 * Upstream vulnerable revision:
 *   b628ba78711bc28327dc7d2d5c074a00f061884e
 *
 * Upstream fixed revision:
 *   7f4d5dc162b77c362a34a0d52949f7a3e1b16d81
 *
 * Reduction classification:
 *   independently-written-equivalent-reduction
 *
 * Relationship to upstream:
 *   Models the separate-translation-unit conditional-move strategy used to
 *   prevent the caller from rediscovering the binary secret condition.
 *
 * Secret inputs:
 *   bit
 *
 * Public inputs:
 *   if_zero and if_one values
 *
 * Expected confidentiality issue:
 *   No issue is expected inside this helper when it remains mask based; it is
 *   the fixed counterpart to the vulnerable branch-lowering case.
 *
 * Canonical compiler command:
 *   clang -Os -fno-vectorize -fno-slp-vectorize -c clangover_ct_cmov.c
 *
 * License note:
 *   This independently written helper contains no copied upstream source.
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
