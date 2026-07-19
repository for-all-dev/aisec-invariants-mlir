/*
 * Case: KyberSlash1 / poly_tomsg vulnerable reduction
 *
 * Upstream repository:
 *   https://github.com/pq-crystals/kyber
 *
 * Original vulnerable code:
 *   https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L180-L198
 *
 * Original fixed code:
 *   https://github.com/pq-crystals/kyber/commit/dda29cc63af721981ee2c831cf00822e69be3220
 *
 * Upstream symbol:
 *   poly_tomsg
 *
 * Upstream vulnerable revision:
 *   b628ba78711bc28327dc7d2d5c074a00f061884e
 *
 * Upstream fixed revision:
 *   dda29cc63af721981ee2c831cf00822e69be3220
 *
 * Reduction classification:
 *   faithful-minimal-reduction
 *
 * Relationship to upstream:
 *   Retains only the secret-derived division and final bit extraction.
 *
 * Secret inputs:
 *   coefficient
 *
 * Public inputs:
 *   KYBER_Q and arithmetic constants
 *
 * Expected confidentiality issue:
 *   Variable-time division on a secret-derived numerator.
 *
 * Canonical compiler command:
 *   clang -O0 -Xclang -disable-O0-optnone --target=aarch64-unknown-linux-gnu -S -emit-llvm kyberslash1_poly_tomsg_vulnerable.c
 *
 * License note:
 *   This is a minimal reduction. Consult the linked upstream source for the
 *   original implementation and license.
 */
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;

__attribute__((noinline))
uint8_t kyberslash1_poly_tomsg_vulnerable(uint16_t coefficient) {
  unsigned int t = coefficient;
  return (uint8_t)((((t << 1) + 1664u) / 3329u) & 1u);
}
