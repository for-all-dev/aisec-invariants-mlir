/*
 * Case: release delivered to two principals who are both authorized
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-actor-model-control
 *
 * Relationship to upstream:
 *   Written for this harness as the policy counterfactual to
 *   audience-mismatch/bad; no upstream body is copied.
 *
 * Secret inputs:
 *   logits
 *
 * Public inputs:
 *   the world-public static release policy and its declared audience.
 *
 * Expected confidentiality behavior:
 *   The masked class is transferred to Alice and Bob, and both principals are
 *   members of the release audience. Every coalition that can see either
 *   endpoint is therefore authorized for the release.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include \
 *     -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm audience_mismatch_authorized.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_HELPER("masked-class")
static unsigned sps_release_authorized_class_candidate(unsigned raw) {
  return raw & 0xffu;
}

extern void sps_transfer_authorized_alice(unsigned value);
extern void sps_transfer_authorized_bob(unsigned value);

SPS_ENTRY("audience_mismatch_authorized")
void audience_mismatch_authorized(unsigned logits SPS_COMPONENT("logits")) {
  unsigned released = sps_release_authorized_class_candidate(logits);
  sps_transfer_authorized_alice(released);
  sps_transfer_authorized_bob(released);
}
