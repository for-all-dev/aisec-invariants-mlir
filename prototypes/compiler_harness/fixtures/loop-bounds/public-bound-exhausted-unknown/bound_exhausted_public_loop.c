/*
 * Case: public bound-exhaustion refusal
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-countermodel-encoding
 *
 * Relationship to upstream:
 *   Written for this harness. No upstream body is copied.
 *
 * Secret inputs:
 *   none
 *
 * Public inputs:
 *   public_count, the loop body, and the public_sink target
 *
 * Security intent:
 *   Written for this harness. Both lanes share one public count; an
 * insufficient semantic bound yields Unknown(LoopRemainder), not a leak. The
 * sibling policy.sps.yaml owns visibility and the sibling abi.sps.yaml owns the
 * concrete carrier, root, and alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm bound_exhausted_public_loop.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_ENTRY("bound_exhausted_public_loop")
void bound_exhausted_public_loop(int public_count SPS_COMPONENT("public-count"),
                                 unsigned *public_sink
                                     SPS_ROOT("public-sink")) {
  int i;

  for (i = 0; i < public_count; i++) {
    /* The bundle deliberately chooses a public count above its proof bound. */
  }

  *public_sink = 0u;
}
