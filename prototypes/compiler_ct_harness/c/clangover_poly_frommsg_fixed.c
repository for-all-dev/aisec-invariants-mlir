/*
 * Case: Clangover / ML-KEM poly_frommsg fixed reduction
 *
 * Upstream repository:
 *   https://github.com/pq-crystals/kyber
 *
 * Original vulnerable code:
 *   https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L141-L159
 *
 * Original fixed code:
 *   https://github.com/antoonpurnal/clangover/tree/7f4d5dc162b77c362a34a0d52949f7a3e1b16d81
 *
 * Upstream symbol:
 *   poly_frommsg
 *
 * Upstream vulnerable revision:
 *   b628ba78711bc28327dc7d2d5c074a00f061884e
 *
 * Upstream fixed revision:
 *   7f4d5dc162b77c362a34a0d52949f7a3e1b16d81
 *
 * Reduction classification:
 *   faithful-minimal-reduction
 *
 * Relationship to upstream:
 *   Retains the bit-to-coefficient behavior but calls a separately compiled
 *   constant-time helper, matching the Clangover mitigation strategy.
 *
 * Secret inputs:
 *   msg
 *
 * Public inputs:
 *   loop counters and public coefficient constant 1665
 *
 * Expected confidentiality issue:
 *   The fixed pair should avoid a secret-dependent branch in the caller when
 *   compiled without LTO; the helper becomes the review boundary.
 *
 * Canonical compiler command:
 *   clang -Os -fno-vectorize -fno-slp-vectorize --target=x86_64-unknown-linux-gnu -S clangover_poly_frommsg_fixed.c
 *
 * License note:
 *   This is a minimal reduction. Consult the linked upstream source and
 *   Clangover repository for original implementation and license context.
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
