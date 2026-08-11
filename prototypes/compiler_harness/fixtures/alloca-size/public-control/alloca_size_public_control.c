/*
 * Case: public world-structural allocation control
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-acceptance-fixture
 *
 * Relationship to upstream:
 *   Written for this harness. No upstream body is copied.
 *
 * Secret inputs:
 *   none
 *
 * Public inputs:
 *   public_count and the public_sink target
 *
 * Security intent:
 *   Written for this harness. The public count is the authored allocation-size
 * component and provides the acceptance twin. The sibling policy.sps.yaml owns
 * visibility and the sibling abi.sps.yaml owns the concrete carrier, root, and
 * alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm alloca_size_public_control.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

/* A volatile pointer store prevents optimization from deleting the VLA. */
static unsigned char *volatile scratch_escape;

/* Acceptance twin: public, world-structural size. */
SPS_ENTRY("alloca_size_public_control")
void alloca_size_public_control(unsigned public_count
                                    SPS_COMPONENT("public-count"),
                                unsigned *public_sink SPS_ROOT("public-sink")) {
  unsigned char scratch[public_count];

  scratch[0] = (unsigned char)public_count;
  scratch_escape = scratch;
  *public_sink = 0u;
}
