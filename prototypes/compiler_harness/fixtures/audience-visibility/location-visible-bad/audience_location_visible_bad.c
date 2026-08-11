/*
 * Case: unauthorized observer sees a release through host visibility
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-actor-model-reduction
 *
 * Relationship to upstream:
 *   Written for this harness to distinguish release visibility from release
 *   authorization; no upstream body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the world-public static release and host-visibility policy.
 *
 * Expected confidentiality issue:
 *   Bob observes the compute host and therefore sees the release value, but
 *   host visibility does not add Bob to the Alice-only release audience.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include \
 *     -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm audience_location_visible_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_HELPER("alice-class")
static unsigned sps_release_location_visible_candidate(unsigned raw) {
  return raw & 0xffu;
}

SPS_ENTRY("audience_location_visible_bad")
void audience_location_visible_bad(unsigned secret SPS_COMPONENT("secret")) {
  (void)sps_release_location_visible_candidate(secret);
}
