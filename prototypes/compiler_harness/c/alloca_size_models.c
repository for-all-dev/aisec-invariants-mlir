/*
 * Case: world-structural allocation size, refusal and acceptance twin
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-acceptance-fixture
 *
 * Relationship to upstream:
 *   Written for this harness to cover the section 20 acceptance row requiring
 *   Unknown(AllocaSizeNotWorldStructural) when a reachable allocation's actual
 *   byte size is missing, unproved, or High-dependent. No upstream body is
 *   copied.
 *
 * Secret inputs:
 *   secret_bit, which selects the scratch size in the refusal case
 *
 * Public inputs:
 *   the candidate sizes 64 and 128, public_count in the acceptance case, and the
 *   public sink target
 *
 * Expected confidentiality issue:
 *   Allocation size is named as an observer-visible channel by this harness, yet
 *   before these functions the corpus contained no allocation whose size was in
 *   question.
 *
 *   Refusal case: a secret bit selects between 64 and 128 scratch bytes. The
 *   required disposition is Unknown with the alloca-size reason and the
 *   world-structural size obligation open.
 *
 *   The trap this exists to catch: both candidate sizes lie under one public
 *   upper bound, and an equal CAP does not make the actual size equal. An
 *   implementation that discharges this by clamping to the cap, or by treating a
 *   public bound as a proof of equal size, is wrong. Cap-based checking is the
 *   natural first implementation.
 *
 *   Acceptance case: the same allocation skeleton with a public count carrying a
 *   validated world-structural size binding. This must be verified, otherwise
 *   the refusal above is indistinguishable from a checker that refuses every
 *   dynamic allocation.
 *
 * Independence note:
 *   WorldStructuralAlloca is an independent universal semantic-support
 *   obligation. It is not a consequence of universal definedness, so it must be
 *   tracked as its own binding rather than folded into a definedness check.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm alloca_size_models.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */

/* Refusal case: High-dependent actual size under a single public cap. */
void alloca_size_high_count(int secret_bit, unsigned *public_sink)
{
  unsigned char scratch[128];
  unsigned count = secret_bit ? 64u : 128u;

  scratch[0] = (unsigned char)count;
  *public_sink = 0u;
}

/* Acceptance twin: public, world-structural size. */
void alloca_size_public_control(unsigned public_count, unsigned *public_sink)
{
  unsigned char scratch[128];

  scratch[0] = (unsigned char)public_count;
  *public_sink = 0u;
}
