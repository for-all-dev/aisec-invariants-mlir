/*
 * Case: laundering -- the blend that actually survives lowering
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-compiler-introduced-reduction
 *
 * Relationship to upstream:
 *   Acceptance twin for launder_scan_bad.c and launder_scan_folded_bad.c. The
 *   barrier idiom below is the one used by production cryptographic libraries
 *   (the same construct as Rust's black_box and OpenSSL's value_barrier); no
 *   specific body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   x, the buffer contents at p, and the returned blend
 *
 * Expected confidentiality issue:
 *   None, and unlike its two partners this is MEASURED rather than asserted.
 *
 *   clang 17.0.6 -O2, x86_64-unknown-linux-gnu:
 *     LLVM IR       : 0 select, 0 br i1        -- the mask survives as
 * arithmetic x86-64 asm    : 0 conditional jumps      -- negl/sbbq/andq,
 * unconditional load aarch64 asm   : 0 conditional branches
 *
 * What the barrier does, and why it is needed:
 *   This file differs from launder_scan_folded_bad.c by one line. Without it,
 *   InstCombine recognizes the blend and rewrites it to a select, which the x86
 *   backend then converts to a branch. The barrier makes the mask opaque, so
 * the pattern match fails and the arithmetic is emitted as written.
 *
 *   Note the shape of the fix: the barrier does not ask the optimizer to
 *   preserve anything. It denies the optimizer the information it would need to
 *   act. Every durable mechanism in this area has that shape -- it survives
 *   because there is no decision point at which something could decide
 *   otherwise.
 *
 * Honest limitation:
 *   Inline-asm opacity is a convention, not a specification. Nothing in the C
 * or LLVM standards requires an empty asm block to survive; it survives because
 *   optimizers decline to reason through inline asm. The emitted code must
 *   therefore be CHECKED, not assumed -- which is what the accompanying
 *   integration test does.
 *
 * Canonical compiler command:
 *   clang -I../../../include -O2 --target=x86_64-unknown-linux-gnu -S launder_scan_fixed.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
typedef unsigned long uint64_t;

SPS_ENTRY("launder_scan_fixed")
SPS_RETURN_OUTPUT("return")
uint64_t launder_scan_fixed(int secret SPS_COMPONENT("secret"),
                            uint64_t x SPS_COMPONENT("x"),
                            const uint64_t *p SPS_ROOT("p")) {
  uint64_t v = *p;
  uint64_t mask = (uint64_t)0 - (uint64_t)(secret != 0);
  /* Optimization barrier: the optimizer loses track of mask and cannot
     pattern-match the blend below back into a select. */
  __asm__ volatile("" : "+r"(mask));
  return (v & mask) | (x & ~mask);
}
