/*
 * Case: public bound-adequacy discharge
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
 *   Written for this harness. This is the positive sibling of
 * public-bound-exhausted-unknown. The program, the policy, and the admitted
 * domain are identical; only the declared execution bound differs. Here the
 * bound covers the admitted count, so the retained remainder is unreachable,
 * bound adequacy is discharged, and both low-equal lanes agree on every loop
 * decision. The sibling policy.sps.yaml owns visibility and the sibling
 * abi.sps.yaml owns the concrete carrier, root, and alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm bound_adequate_public_loop.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_ENTRY("bound_adequate_public_loop")
void bound_adequate_public_loop(int public_count SPS_COMPONENT("public-count"),
                                unsigned *public_sink
                                    SPS_ROOT("public-sink")) {
  int i;

  for (i = 0; i < public_count; i++) {
    /* The bundle admits public_count == 8 and declares a bound of 8, so the
     * loop block executes exactly 8 times and the remainder is never reached.
     * A bound of 7 would make this fixture its Unknown(LoopRemainder) sibling.
     */
  }

  *public_sink = 0u;
}
