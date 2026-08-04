/*
 * Unit proof: sequential self-composition of leftoverlocals_scratch_bad.
 *
 * Models LeftoverLocals: GPU local memory is not cleared between tenants, so a
 * later tenant reads whatever the earlier one left behind.
 *
 *   secrets = prior_tenant_secret            (differs between the two runs)
 *   public  = next_tenant_public_value       (shared by both runs)
 *   Obs     = (*shared_scratch, *next_tenant_output, return value)
 *
 * The scratch buffer is IN the observation, not just the output. That is the
 * actual vulnerability: the residue is readable by the next tenant whether or
 * not the program hands it over. Dropping it from Obs would still separate the
 * two fixtures here, but would be modelling a weaker attacker than the CVE.
 *
 * EXPECTED: sat. The bad variant stores the prior tenant's secret into the
 * shared scratch and reads it straight back out, so two runs differing only in
 * that secret are distinguishable. The counterexample IS the witness.
 *
 * Each run gets its OWN scratch and output cells. Sharing them between the two
 * runs would be modelling one execution, not two, and the assertion would then
 * be comparing a cell with itself.
 *
 * Needs no metadata flags: the leak is in a value the observer reads directly.
 *
 * Calibrate against leftoverlocals_scratch_fixed_harness.c, which must be
 * unsat. A single verdict here means nothing on its own.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/leftoverlocals_scratch_bad.c"

extern uint32_t nd_u32(void);

int main(void) {
  uint32_t pub = nd_u32(); /* the next tenant's own input, shared by both runs */

  uint32_t s0 = nd_u32(); /* prior tenant's secret, run 0 */
  uint32_t s1 = nd_u32(); /* prior tenant's secret, run 1 */

  uint32_t scratch0 = 0u, out0 = 0u;
  uint32_t scratch1 = 0u, out1 = 0u;

  uint32_t r0 = leftoverlocals_scratch_bad(s0, pub, &scratch0, &out0);
  uint32_t r1 = leftoverlocals_scratch_bad(s1, pub, &scratch1, &out1);

  sassert(scratch0 == scratch1 && out0 == out1 && r0 == r1);

  return 0;
}
