/*
 * Case: equal authorized release followed by an unauthorized secret transfer
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-actor-model-reduction
 *
 * Relationship to upstream:
 *   Written for this harness to exercise EqualAuthorized ledger behavior; no
 *   upstream body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the world-public static release policy.
 *
 * Expected confidentiality issue:
 *   Both lanes release zero to an authorized observer. Equality does not
 *   retire the outstanding secret obligation, so the later secret transfer
 *   remains a counterexample.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include \
 *     -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm audience_equal_release_then_leak_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_HELPER("zero-release")
static unsigned sps_release_zero_candidate(unsigned raw) {
  (void)raw;
  return 0u;
}

extern void sps_transfer_equal_release_observer(unsigned value);

SPS_ENTRY("audience_equal_release_then_leak_bad")
void audience_equal_release_then_leak_bad(
    unsigned secret SPS_COMPONENT("secret")) {
  unsigned released = sps_release_zero_candidate(secret);
  (void)released;
  sps_transfer_equal_release_observer(secret);
}
