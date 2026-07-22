/*
 * Case: Clangover / ML-KEM poly_frommsg vulnerable reduction
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
 *   Retains only message-bit extraction, mask construction, and coefficient
 *   assignment from the Kyber/ML-KEM reference idiom used by Clangover.
 *
 * Secret inputs:
 *   msg
 *
 * Public inputs:
 *   loop counters and public coefficient constant 1665
 *
 * Expected confidentiality issue:
 *   Branchless source may be lowered by selected Clang/LLVM configurations
 *   into a secret-dependent x86 conditional branch.
 *
 * Canonical compiler command:
 *   clang -Os -fno-vectorize -fno-slp-vectorize --target=x86_64-unknown-linux-gnu -S clangover_poly_frommsg_vulnerable.c
 *
 * License note:
 *   This is a minimal reduction. Consult the linked upstream source and
 *   Clangover repository for original implementation and license context.
 */
typedef unsigned char uint8_t;
typedef signed short int16_t;

__attribute__((noinline))
void clangover_poly_frommsg_vulnerable(int16_t out[256], const uint8_t msg[32]) {
  for (unsigned i = 0; i < 32; ++i) {
    for (unsigned j = 0; j < 8; ++j) {
      int16_t bit = (int16_t)((msg[i] >> j) & 1u);
      int16_t mask = (int16_t)-bit;
      out[8 * i + j] = (int16_t)(mask & 1665);
    }
  }
}
