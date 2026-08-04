/*
 * Unit proof: sequential self-composition of redis_pool_reuse_bad.
 *
 * Models a connection-pool cross-tenant leak: a cancelled request leaves a
 * response on the pooled connection, and the next borrower receives it.
 *
 *   secrets = response_owned_by_a                        (differs per run)
 *   public  = response_owned_by_b, request_a_was_cancelled  (shared)
 *   Obs     = return value
 *
 * The observer is actor B. A's response is the secret precisely because B must
 * never see it; B's own response is theirs already, so it is shared.
 *
 * request_a_was_cancelled is shared rather than per-run. It is a property of
 * the schedule, not of either tenant's data, and holding it equal makes the
 * question the sharp one: given the SAME cancellation history, can B tell two
 * different A-responses apart?
 *
 * EXPECTED: sat. The bad variant hands back A's response whenever the
 * cancellation flag is odd, so B distinguishes the two runs directly.
 *
 * Needs no metadata flags -- the leak is in a value the observer reads directly.
 *
 * Calibrate against redis_pool_reuse_fixed_harness.c, which must be unsat.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/redis_pool_reuse_bad.c"

extern uint32_t nd_u32(void);

int main(void) {
  /* Each run gets its OWN public inputs, related by an assumed equality rather
   * than by sharing one variable. Matching the fixed harness exactly matters:
   * the two verdicts are only comparable if the encoding is the same. The
   * reason the fixed harness needs this form is documented there. */
  uint32_t b0 = nd_u32(), b1 = nd_u32();
  uint32_t c0 = nd_u32(), c1 = nd_u32();

  assume(b0 == b1); /* equal public inputs: the premise, not an encoding */
  assume(c0 == c1);

  uint32_t a0 = nd_u32(); /* run 0 secret: A's response */
  uint32_t a1 = nd_u32(); /* run 1 secret: A's response */

  uint32_t r0 = redis_pool_reuse_bad(a0, b0, c0);
  uint32_t r1 = redis_pool_reuse_bad(a1, b1, c1);

  sassert(r0 == r1);

  return 0;
}
