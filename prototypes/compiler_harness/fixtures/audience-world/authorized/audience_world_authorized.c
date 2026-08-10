/*
 * Case: world-authorized release followed by a world-visible transfer
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-actor-model-control
 *
 * Relationship to upstream:
 *   Written for this harness to exercise world audience semantics; no
 *   upstream body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the world-public static release policy.
 *
 * Expected confidentiality behavior:
 *   The unequal masked release is authorized for every coalition, including
 *   the empty coalition, before the same value reaches the public endpoint.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include \
 *     -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm audience_world_authorized.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_HELPER("world-class")
static unsigned sps_release_world_class_candidate(unsigned raw) {
  return raw & 0xffu;
}

extern void sps_transfer_world_endpoint(unsigned value);

SPS_ENTRY("audience_world_authorized")
void audience_world_authorized(unsigned secret SPS_COMPONENT("secret")) {
  unsigned released = sps_release_world_class_candidate(secret);
  sps_transfer_world_endpoint(released);
}
