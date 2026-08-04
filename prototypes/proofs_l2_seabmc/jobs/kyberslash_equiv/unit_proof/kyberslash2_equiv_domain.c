/*
 * Equivalence proof: kyberslash2_compress_vulnerable == ..._fixed, restricted
 * to the domain the rewrite is actually valid on.
 *
 * EXPECTED: unsat -- under c < q the two agree.
 *
 * This is the repair for the gap kyberslash2_equiv_full.c exhibits. That file
 * shows the unrestricted claim is FALSE (49 counterexamples over uint16, first
 * at c = 13212, from uint32 wraparound in `t *= 80635u`). This file states the
 * missing precondition explicitly and proves the claim under it, over all
 * inputs rather than by enumeration.
 *
 * The precondition is not invented for the proof: it is Kyber's own. A
 * polynomial coefficient is reduced mod q = KYBER_Q = 3329 before compression,
 * so c < q holds at every real call site. What was missing is that nothing said
 * so -- compiler_harness/c/equivalence_driver.c:125-132 encodes it as a loop
 * bound and never names it, so a reader cannot tell the bound is load-bearing
 * rather than a sampling choice. Here it is a premise, and the pair of verdicts
 * (full = sat, domain = unsat) locates the boundary exactly.
 */

#include "seahorn/seahorn.h"

/* The fixtures under test, used in place -- not copied. See the note in
 * kyberslash1_equiv.c about the duplicated uint8_t/uint16_t typedefs. */
#include "../../../../compiler_harness/c/kyberslash2_compress_vulnerable.c"
#include "../../../../compiler_harness/c/kyberslash2_compress_fixed.c"

/* KYBER_Q. The fixtures hard-code 3329 rather than naming it. */
#define KYBERSLASH_Q 3329u

extern unsigned int nd_u32(void);

int main(void) {
  uint16_t c = (uint16_t)nd_u32();

  /* The precondition every real caller satisfies: coefficients are reduced
   * mod q before compression. */
  assume(c < KYBERSLASH_Q);

#ifdef SEA_PROBE
  /* Reachability probe, expected `sat`. See kyberslash1_equiv.c for what it
   * rules out. It matters more here than there, because this file HAS an
   * `assume`: were that premise unsatisfiable, the proof below would report a
   * meaningless `unsat`. c = 0 satisfies c < q and yields 1664/3329 & 15 == 0,
   * so a model exists. */
  sassert(kyberslash2_compress_vulnerable(c) == 0);
#else
  sassert(kyberslash2_compress_vulnerable(c) == kyberslash2_compress_fixed(c));
#endif

  return 0;
}
