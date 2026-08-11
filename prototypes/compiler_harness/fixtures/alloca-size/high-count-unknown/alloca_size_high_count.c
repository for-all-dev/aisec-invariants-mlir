/*
 * Case: High-dependent allocation size refusal
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
 *   secret_bit
 *
 * Public inputs:
 *   the candidate sizes 64 and 128 and the public_sink target
 *
 * Security intent:
 *   Written for this harness. A secret bit selects the actual VLA size, leaving
 * WorldStructuralAlloca open. The sibling policy.sps.yaml owns visibility and
 * the sibling abi.sps.yaml owns the concrete carrier, root, and alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm alloca_size_high_count.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

/* A volatile pointer store prevents optimization from deleting the VLA. */
static unsigned char *volatile scratch_escape;

/* Refusal case: High-dependent actual size under a single public cap. */
SPS_ENTRY("alloca_size_high_count")
void alloca_size_high_count(int secret_bit SPS_COMPONENT("secret-bit"),
                            unsigned *public_sink SPS_ROOT("public-sink")) {
  unsigned count = secret_bit ? 64u : 128u;
  unsigned char scratch[count];

  scratch[0] = (unsigned char)count;
  scratch_escape = scratch;
  *public_sink = 0u;
}
