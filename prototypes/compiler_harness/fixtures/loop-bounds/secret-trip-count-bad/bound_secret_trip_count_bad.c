/*
 * Case: secret loop trip-count counterexample
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
 *   secret_count
 *
 * Public inputs:
 *   the loop body, zero sentinel, and public_sink target
 *
 * Security intent:
 *   Written for this harness. The secret count changes the public control trace
 * before any proof-bound exhaustion. The sibling policy.sps.yaml owns
 * visibility and the sibling abi.sps.yaml owns the concrete carrier, root, and
 * alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm bound_secret_trip_count_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
SPS_ENTRY("bound_secret_trip_count_bad")
void bound_secret_trip_count_bad(int secret_count SPS_COMPONENT("secret-count"),
                                 unsigned *public_sink
                                     SPS_ROOT("public-sink")) {
  int i;

  for (i = 0; i < secret_count; i++) {
    /* Body is deliberately empty: the channel is the backedge count. */
  }

  *public_sink = 0u;
}
