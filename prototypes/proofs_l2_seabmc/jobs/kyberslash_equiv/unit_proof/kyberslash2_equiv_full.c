/*
 * Equivalence proof: kyberslash2_compress_vulnerable == ..._fixed over the
 * WHOLE uint16 domain, with no precondition.
 *
 * EXPECTED: sat. The two do NOT agree everywhere, and the counterexample is
 * the point of this file.
 *
 * compiler_harness/c/equivalence_driver.c:125-132 checks this pair by
 * enumeration over c in [0, 3329) -- but the parameter is uint16_t, so
 * 3329..65535 were never tested. Exhaustive evaluation of that untested range
 * finds 49 disagreements, the first at c = 13212. They come from uint32
 * wraparound in the fixed variant: `t <<= 4` then `t *= 80635u` reaches roughly
 * 8.5e10 for large c, well past 2^32.
 *
 * So the driver's loop bound silently encodes a precondition that nothing
 * states: the rewrite is valid for coefficients below q = 3329, not for every
 * uint16_t the signature accepts. That is a real (if benign-in-context) gap --
 * benign only for as long as every caller respects the range, which no checked
 * artifact currently asserts.
 *
 * This job's `sat` also serves as the CALIBRATION for the other two claims in
 * this directory. kyberslash1_equiv.c and kyberslash2_equiv_domain.c both
 * report `unsat`, and an `unsat` alone is indistinguishable from a proof that
 * checks nothing. This file uses the same harness shape, the same flags and the
 * same include-the-fixture-in-place structure, and comes back `sat` -- which is
 * what shows the shape can see an inequivalence when one is there.
 *
 * Together with kyberslash2_equiv_domain.c this bounds the disagreement
 * exactly: it exists over uint16, and it vanishes under c < q.
 */

#include "seahorn/seahorn.h"

/* The fixtures under test, used in place -- not copied. See the note in
 * kyberslash1_equiv.c about the duplicated uint8_t/uint16_t typedefs. */
#include "../../../../compiler_harness/c/kyberslash2_compress_vulnerable.c"
#include "../../../../compiler_harness/c/kyberslash2_compress_fixed.c"

extern unsigned int nd_u32(void);

int main(void) {
  uint16_t c = (uint16_t)nd_u32();

  /* No `assume`. The claim under test is the unrestricted one, and it fails. */
  sassert(kyberslash2_compress_vulnerable(c) == kyberslash2_compress_fixed(c));

  return 0;
}
