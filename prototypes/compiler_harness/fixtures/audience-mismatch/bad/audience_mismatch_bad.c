/*
 * Case: release delivered outside its declared audience
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-actor-model-reduction
 *
 * Relationship to upstream:
 *   Written for this harness. Promoted from examples/actors/t1 once the
 * metadata contract could express per-coalition result rows; no upstream body
 * is copied.
 *
 * Secret inputs:
 *   logits
 *
 * Public inputs:
 *   the world-public static release policy and its declared audience. The two
 *   pointer arguments are structural channel roots whose visibility is assigned
 *   by the case-local policy rather than by their C types.
 *
 * Expected confidentiality issue:
 *   One value is released exactly once, under a policy whose declared audience
 *   is {alice}. It is then delivered to two principal channels. The two stores
 *   are identical apart from their destination.
 *
 *   For coalitions containing alice, the prefix-causal release ledger retires
 *   the matching obligation. For {bob}, the carrier payload remains concealed,
 *   the obligation stays active, and the later Bob-visible store reaches Bad.
 *
 * Why this fixture exists at all:
 *   It is the reason the result record is keyed by (entry, coalition) rather
 *   than by a single observer. The product is safe at {alice} and has a
 *   replayable counterexample at {bob}, with no containment relation between
 *   those coalitions -- so a
 *   checker that evaluates only the authored maximal coalition {alice,bob}
 *   never visits {bob} alone and reports the artifact clean.
 *
 *   Before the record carried result rows this scenario was unrepresentable,
 * and lived in examples/actors/ as a design sketch no tool read.
 *
 * Note on the empty and joint coalitions:
 *   The empty coalition sees neither principal channel, so the projected
 * payload trace remains equal. The joint coalition contains alice, so the
 * release is authorized for it. World-level structure remains lockstep in both
 * cases; only {bob} obtains the replayable audience-mismatch witness.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include \
 *     -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm audience_mismatch_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

/*
 * Modeled release wrapper. It is case-local so intentionally duplicated cases
 * cannot collide when the corpus is linked into the equivalence driver.
 */
SPS_HELPER("masked-class")
static unsigned sps_release_masked_class_candidate(unsigned raw) {
  return raw & 0xffu;
}

SPS_ENTRY("audience-mismatch")
void audience_mismatch_bad(unsigned logits SPS_COMPONENT("logits"),
                           unsigned *alice_channel SPS_ROOT("alice-channel"),
                           unsigned *bob_channel SPS_ROOT("bob-channel")) {
  unsigned released = sps_release_masked_class_candidate(logits);

  /* Authorized: Alice is the declared audience of masked-class. */
  *alice_channel = released;

  /* NOT authorized for {bob}. Byte-identical operation, different verdict. */
  *bob_channel = released;
}
