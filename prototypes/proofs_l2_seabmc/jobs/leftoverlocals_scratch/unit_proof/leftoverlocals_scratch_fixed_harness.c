/*
 * Unit proof: sequential self-composition of leftoverlocals_scratch_fixed.
 *
 * Identical to leftoverlocals_scratch_bad_harness.c in every respect except the
 * fixture it includes. That is deliberate: the two verdicts are only comparable
 * if the observation, the secrets and the shared public input are the same.
 *
 *   secrets = prior_tenant_secret            (differs between the two runs)
 *   public  = next_tenant_public_value       (shared by both runs)
 *   Obs     = (*shared_scratch, *next_tenant_output, return value)
 *
 * EXPECTED: unsat. The fixed variant overwrites the scratch with the next
 * tenant's own public value before reading it back, so nothing the observer
 * sees depends on the prior tenant's secret.
 *
 * This verdict is only informative because the bad harness returns sat under
 * the same observation.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/leftoverlocals_scratch_fixed.c"

extern uint32_t nd_u32(void);

int main(void) {
  uint32_t pub = nd_u32(); /* the next tenant's own input, shared by both runs */

  uint32_t s0 = nd_u32(); /* prior tenant's secret, run 0 */
  uint32_t s1 = nd_u32(); /* prior tenant's secret, run 1 */

  uint32_t scratch0 = 0u, out0 = 0u;
  uint32_t scratch1 = 0u, out1 = 0u;

  uint32_t r0 = leftoverlocals_scratch_fixed(s0, pub, &scratch0, &out0);
  uint32_t r1 = leftoverlocals_scratch_fixed(s1, pub, &scratch1, &out1);

  sassert(scratch0 == scratch1 && out0 == out1 && r0 == r1);

  return 0;
}
