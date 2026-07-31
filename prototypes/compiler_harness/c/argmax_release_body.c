/*
 * Case: admissible release body / normal-form fragment boundary (positive side)
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   synthetic-minimal-reduction
 *
 * Relationship to upstream:
 *   Not derived from an upstream CVE. This is the positive control for
 *   sha256_round_release_body.c: a release body that IS inside the rev-4
 *   accepted fragment.
 *
 * Secret inputs:
 *   logits
 *
 * Public inputs:
 *   the loop bound 10 and the class-index domain
 *
 * Expected confidentiality issue:
 *   None. This file is not a leak fixture; it is a normal-form fixture.
 *
 * What it demonstrates:
 *   Bounded argmax is one of the corpus's V1 release types -- "bounded
 *   fixed-width bitvectors, bounded tuples of those values, and bounded argmax"
 *   -- and its body compiles to loads at public offsets, integer compares, and
 *   selects. Every one of those is inside profile section 6.5's accepted integer
 *   surface, and the body contains no intrinsic at all.
 *
 *   Two details are load-bearing and easy to get wrong when writing an argmax
 *   declassifier:
 *
 *   1. The running maximum is kept in a VALUE (bv), not re-loaded through the
 *      current best INDEX. Writing logits[bi] would make the load address depend
 *      on the secret, turning a clean release body into a secret-dependent
 *      address -- a Memory event whose byte offset differs between lanes.
 *
 *   2. The comparison feeds a select, not a branch, so control flow depends only
 *      on the public trip count.
 *
 *   The tie rule matters for conformance rather than for the fragment: rev-4's
 *   V1 argmax selects the LOWEST index among equal maxima, which is what the
 *   strict `>` comparison below implements.
 *
 * Canonical compiler command:
 *   clang -std=c11 -O2 --target=x86_64-unknown-linux-gnu -S -emit-llvm \
 *     argmax_release_body.c
 *
 * License note:
 *   Written for this harness; no upstream code is reproduced.
 */
typedef unsigned int uint32_t;
typedef signed int int32_t;

__attribute__((noinline))
uint32_t argmax_release_body(const int32_t logits[10]) {
  int32_t bv = logits[0];
  uint32_t bi = 0u;
  for (uint32_t i = 1u; i < 10u; ++i) {
    int32_t v = logits[i];
    uint32_t gt = (uint32_t)(v > bv);
    bv = gt ? v : bv;
    bi = gt ? i : bi;
  }
  return bi;
}
