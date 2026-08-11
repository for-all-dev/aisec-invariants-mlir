/*
 * Case: unauthorized release and transfer remain concealed
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-actor-model-control
 *
 * Relationship to upstream:
 *   Written for this harness to exercise concealed unauthorized releases; no
 *   upstream body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the world-public static release and host-visibility policy.
 *
 * Expected confidentiality behavior:
 *   Bob is not authorized, but can see neither the release host nor the
 *   concealed destination. His obligation remains active without reaching a
 *   projected unequal observation.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include \
 *     -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm audience_unauthorized_concealed.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_HELPER("alice-class")
static unsigned sps_release_alice_class_candidate(unsigned raw) {
  return raw & 0xffu;
}

extern void sps_transfer_concealed_endpoint(unsigned value);

SPS_ENTRY("audience_unauthorized_concealed")
void audience_unauthorized_concealed(
    unsigned secret SPS_COMPONENT("secret")) {
  unsigned released = sps_release_alice_class_candidate(secret);
  sps_transfer_concealed_endpoint(released);
}
