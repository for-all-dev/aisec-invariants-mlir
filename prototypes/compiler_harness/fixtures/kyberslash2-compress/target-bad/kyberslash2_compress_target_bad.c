/*
 * Case: synthetic KyberSlash2 / poly_compress target-control oracle
 *
 * Original vulnerable code:
 *   https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L23-L32
 *
 * Reduction classification:
 *   synthetic-target-control-reduction
 *
 * Relationship to upstream:
 *   Keeps the vulnerable poly_compress arithmetic, but adds a semantically
 *   redundant zero case so the hand-authored target model has an explicit
 *   secret-dependent successor choice. This is synthetic test data, not a
 *   claim that a particular compiler emits this control flow.
 *
 * Secret inputs:
 *   coefficient
 *
 * Public inputs:
 *   arithmetic constants
 *
 * Canonical compiler command:
 *   clang -I../../../include -O0 -S -emit-llvm kyberslash2_compress_target_bad.c
 *
 * License note:
 *   This independently written synthetic reduction contains no copied Kyber
 *   source. Consult the linked upstream source for license context.
 */
#include <sps/annotations.h>
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;

SPS_ENTRY("kyberslash2_compress_target_bad")
SPS_RETURN_OUTPUT("return")
__attribute__((noinline)) uint8_t kyberslash2_compress_target_bad(
    uint16_t coefficient SPS_COMPONENT("coefficient")) {
  if (coefficient == 0u)
    return 0u;

  unsigned int t = coefficient;
  return (uint8_t)((((t << 4) + 1664u) / 3329u) & 15u);
}
