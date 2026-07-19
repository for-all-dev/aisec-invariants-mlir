/*
 * Case: KyberSlash2 / poly_compress vulnerable reduction
 *
 * Upstream repository:
 *   https://github.com/pq-crystals/kyber
 *
 * Original vulnerable code:
 *   https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L23-L32
 *
 * Original fixed code:
 *   https://github.com/pq-crystals/kyber/commit/11d00ff1f20cfca1f72d819e5a45165c1e0a2816
 *
 * Upstream symbol:
 *   poly_compress
 *
 * Upstream vulnerable revision:
 *   b628ba78711bc28327dc7d2d5c074a00f061884e
 *
 * Upstream fixed revision:
 *   11d00ff1f20cfca1f72d819e5a45165c1e0a2816
 *
 * Reduction classification:
 *   faithful-minimal-reduction
 *
 * Relationship to upstream:
 *   Retains one secret-derived compression division and final four-bit mask.
 *
 * Secret inputs:
 *   coefficient
 *
 * Public inputs:
 *   KYBER_Q and arithmetic constants
 *
 * Expected confidentiality issue:
 *   Variable-time division on a secret-derived compression numerator.
 *
 * Canonical compiler command:
 *   clang -O0 -Xclang -disable-O0-optnone --target=aarch64-unknown-linux-gnu -S -emit-llvm kyberslash2_compress_vulnerable.c
 *
 * License note:
 *   This is a minimal reduction. Consult the linked upstream source for the
 *   original implementation and license.
 */
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;

__attribute__((noinline))
uint8_t kyberslash2_compress_vulnerable(uint16_t coefficient) {
  unsigned int t = coefficient;
  return (uint8_t)((((t << 4) + 1664u) / 3329u) & 15u);
}
