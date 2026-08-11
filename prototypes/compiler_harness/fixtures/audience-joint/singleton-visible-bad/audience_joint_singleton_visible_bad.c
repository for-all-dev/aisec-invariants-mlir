/*
 * Case: joint-only release delivered to an Alice-only endpoint
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-actor-model-reduction
 *
 * Relationship to upstream:
 *   Written for this harness to distinguish joint AND from member OR
 *   semantics; no upstream body is copied.
 *
 * Secret inputs:
 *   logits
 *
 * Public inputs:
 *   the world-public static joint release policy.
 *
 * Expected confidentiality issue:
 *   Alice alone sees the transferred class, but the release audience requires
 *   the coalition containing both Alice and Bob.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include \
 *     -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm audience_joint_singleton_visible_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_HELPER("joint-class")
static unsigned sps_release_joint_singleton_candidate(unsigned raw) {
  return raw & 0xffu;
}

extern void sps_transfer_joint_to_alice(unsigned value);

SPS_ENTRY("audience_joint_singleton_visible_bad")
void audience_joint_singleton_visible_bad(
    unsigned logits SPS_COMPONENT("logits")) {
  unsigned released = sps_release_joint_singleton_candidate(logits);
  sps_transfer_joint_to_alice(released);
}
