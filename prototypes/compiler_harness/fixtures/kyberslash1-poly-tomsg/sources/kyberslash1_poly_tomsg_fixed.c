/*
 * Case: KyberSlash1 / poly_tomsg fixed reduction
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
 *   Replaces the division with the upstream multiply/add/shift formula while
 *   preserving the final bit extraction.
 *
 * Secret inputs:
 *   coefficient
 *
 * Public inputs:
 *   KYBER_Q-derived constants
 *
 * Expected confidentiality issue:
 *   The fixed reduction should contain no secret-derived division.
 *
 * Canonical compiler command:
 *   clang -O0 -Xclang -disable-O0-optnone --target=aarch64-unknown-linux-gnu -S -emit-llvm kyberslash1_poly_tomsg_fixed.c
 *
 * License note:
 *   This is a minimal reduction. Consult the linked upstream source for the
 *   original implementation and license.
 */
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;

__attribute__((noinline))
uint8_t kyberslash1_poly_tomsg_fixed(uint16_t coefficient) {
  unsigned int t = coefficient;
  t <<= 1;
  t += 1665u;
  t *= 80635u;
  t >>= 28;
  return (uint8_t)(t & 1u);
}
