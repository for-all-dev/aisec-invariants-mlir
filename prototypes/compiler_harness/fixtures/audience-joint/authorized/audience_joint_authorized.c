/*
 * Case: jointly authorized release delivered to a joint-only endpoint
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-actor-model-control
 *
 * Relationship to upstream:
 *   Written for this harness to exercise joint audience semantics; no
 *   upstream body is copied.
 *
 * Secret inputs:
 *   logits
 *
 * Public inputs:
 *   the world-public static joint release policy.
 *
 * Expected confidentiality behavior:
 *   Neither singleton coalition can observe the joint endpoint. The coalition
 *   containing both Alice and Bob can observe it and is authorized.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include \
 *     -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm audience_joint_authorized.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_HELPER("joint-class")
static unsigned sps_release_joint_class_candidate(unsigned raw) {
  return raw & 0xffu;
}

extern void sps_transfer_joint_endpoint(unsigned value);

SPS_ENTRY("audience_joint_authorized")
void audience_joint_authorized(unsigned logits SPS_COMPONENT("logits")) {
  unsigned released = sps_release_joint_class_candidate(logits);
  sps_transfer_joint_endpoint(released);
}
