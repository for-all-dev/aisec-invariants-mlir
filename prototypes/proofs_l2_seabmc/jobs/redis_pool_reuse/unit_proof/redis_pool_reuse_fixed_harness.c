/*
 * Unit proof: sequential self-composition of redis_pool_reuse_fixed.
 *
 *   secrets = response_owned_by_a                        (differs per run)
 *   public  = response_owned_by_b, request_a_was_cancelled  (shared)
 *   Obs     = return value
 *
 * EXPECTED: unsat. The fixed variant always returns B's own response, ignoring
 * both A's response and the cancellation flag, so B cannot distinguish the runs.
 *
 * WHY THIS HARNESS STATES ITS PUBLIC INPUTS AS A PREMISE. Every other job here
 * gives the two runs the same public variable. Doing that HERE produces a
 * vacuous proof: the fixed fixture returns its second argument unchanged, so
 * after inlining r0 and r1 become the same SSA value, clang folds r0 == r1 to
 * true before SeaHorn ever runs, and sea reports "The program has no main()
 * function / Possibly all assertions have been discharged by the front-end"
 * with no verdict at all. Nothing was proved.
 *
 * Giving each run its own b/c and relating them with `assume` fixes it, and is
 * the more faithful encoding anyway: "equal public inputs" is a HYPOTHESIS of
 * the theorem, and `assume` is opaque to clang, so the equality has to be
 * discharged by the solver instead of by the constant folder. The property is
 * identical; only the encoding differs.
 *
 * This verdict is only informative because the bad harness returns sat under
 * the same observation.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/redis_pool_reuse_fixed.c"

extern uint32_t nd_u32(void);

int main(void) {
  /* Each run gets its OWN public inputs, related by an assumed equality rather
   * than by sharing one variable. See the note above on why. */
  uint32_t b0 = nd_u32(), b1 = nd_u32();
  uint32_t c0 = nd_u32(), c1 = nd_u32();

  assume(b0 == b1); /* equal public inputs: the premise, not an encoding */
  assume(c0 == c1);

  uint32_t a0 = nd_u32(); /* run 0 secret: A's response */
  uint32_t a1 = nd_u32(); /* run 1 secret: A's response */

  uint32_t r0 = redis_pool_reuse_fixed(a0, b0, c0);
  uint32_t r1 = redis_pool_reuse_fixed(a1, b1, c1);

  sassert(r0 == r1);

  return 0;
}
