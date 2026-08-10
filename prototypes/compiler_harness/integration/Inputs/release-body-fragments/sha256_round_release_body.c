/*
 * Case: hash-valued release body / normal-form fragment boundary
 *
 * Upstream repository:
 *   https://github.com/pq-crystals/kyber  (ML-KEM uses SHA-2/SHA-3 throughout)
 *
 * Reference for the round function:
 *   FIPS 180-4, section 6.2.2 (SHA-256 round), Sigma1 and Ch
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   faithful-minimal-reduction
 *
 * Relationship to upstream:
 *   Retains only one SHA-256 round's Sigma1 and Ch terms and the working-variable
 *   update. Nothing about the message schedule, padding, or state array is
 *   modelled. That is sufficient, because the property under test is a property
 *   of the ROTATION idiom, which every SHA-2 implementation contains.
 *
 * Secret inputs:
 *   e, f, g, h  (working variables derived from the key/message)
 *
 * Public inputs:
 *   k, w  (round constant and expanded message word)
 *
 * Expected confidentiality issue:
 *   None. This file is not a leak fixture. It is a NORMAL-FORM fixture.
 *
 * What it demonstrates:
 *   A rotation-based hash body cannot enter the rev-4 accepted fragment. The
 *   pinned pipeline canonicalises (x >> n) | (x << (32 - n)) into the funnel
 *   shift intrinsics llvm.fshl / llvm.fshr. Profile section 6.5's accepted
 *   integer family is add sub mul udiv sdiv urem srem shl lshr ashr and or xor,
 *   closing with "Every other LLVM instruction is rejected"; section 6.6's
 *   accepted residual intrinsics are exactly memcpy, memmove, memset,
 *   lifetime.start, lifetime.end, trap, ubsantrap and dbg.*, closing with "All
 *   other residual intrinsics ... are out of profile". Funnel shift is in
 *   neither list, and no pass in the pinned pipeline expands it.
 *
 *   The consequence is a scope limitation worth stating plainly: rev-4 cannot
 *   express a hash-valued authorized release, because the release BODY is
 *   outside the fragment, before any question about carriers or inlining
 *   arises. This is consistent with the policy side, where SPS-PolicyExpr-NF-v2
 *   has no SHA-256 primitive and an opaque named hash call is not an authorized
 *   release expression.
 *
 * Canonical compiler command:
 *   clang -std=c11 -O2 --target=x86_64-unknown-linux-gnu -S -emit-llvm \
 *     sha256_round_release_body.c
 *
 * License note:
 *   This is a minimal reduction written for this harness. Consult FIPS 180-4 for
 *   the specification of the round function.
 */
typedef unsigned int uint32_t;

static uint32_t rotr(uint32_t x, unsigned n) {
  return (x >> n) | (x << (32u - n));
}

__attribute__((noinline))
uint32_t sha256_round_release_body(uint32_t e, uint32_t f, uint32_t g,
                                   uint32_t h, uint32_t k, uint32_t w) {
  uint32_t s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
  uint32_t ch = (e & f) ^ (~e & g);
  return h + s1 + ch + k + w;
}
