/*
 * Calibration counterpart to explicit_error_oracle_bad_harness.c: the same
 * self-composition, run against the REPAIRED fixture.
 *
 * EXPECTED: unsat. The fixed variant writes a constant 0 to
 * *public_error_detail and ignores padding_error_detail entirely, so once the
 * authorized release (the validity bit) is held equal the two runs are
 * indistinguishable to the observer.
 *
 * This is the positive control that makes the bad harness's `sat` meaningful:
 * it shows the premise R is not so strong that it trivially equates the two
 * runs. If R alone forced every output equal, BOTH harnesses would report unsat
 * and the leaky one would look verified.
 *
 * Note this verdict is what a *correct* declassification looks like -- the API
 * still reveals the validity bit, and that is intended. Only the surplus
 * distinction is a violation.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

#include "../../../../compiler_harness/c/explicit_error_oracle_fixed.c"

extern uint32_t nd_u32(void);

int main(void) {
  uint32_t len = nd_u32(); /* public input, shared by both runs */

  uint32_t v0 = nd_u32(), d0 = nd_u32(); /* run 0 secrets */
  uint32_t v1 = nd_u32(), d1 = nd_u32(); /* run 1 secrets */

  assume(v0 <= 1u);
  assume(v1 <= 1u);

  /* R: the authorized release is held EQUAL across the two runs. */
  assume((1u ^ (v0 & 1u)) == (1u ^ (v1 & 1u)));

  uint32_t st0, ed0, st1, ed1;
  uint32_t r0 = explicit_error_oracle_fixed(v0, d0, len, &st0, &ed0);
  uint32_t r1 = explicit_error_oracle_fixed(v1, d1, len, &st1, &ed1);

  sassert(st0 == st1 && ed0 == ed1 && r0 == r1);

  return 0;
}
