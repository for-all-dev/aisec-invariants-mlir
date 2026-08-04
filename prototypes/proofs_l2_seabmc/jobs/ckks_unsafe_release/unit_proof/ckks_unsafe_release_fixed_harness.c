/*
 * Unit proof: sequential self-composition of ckks_unsafe_release_fixed.
 *
 * Same property, same observation and same release policy as
 * ckks_unsafe_release_bad_harness.c -- only the fixture under test differs.
 *
 *   R       = ckks_sanitize_model(raw, mask, cert)   [L0 policy]
 *   Obs     = *public_release
 *   secrets = raw_approximate_plaintext
 *   public  = public_sanitizer_mask, certificate_ok  (shared by both runs)
 *
 * EXPECTED: unsat. The fixed variant publishes exactly ckks_sanitize_model(...),
 * which is R -- and R is held equal by the premise, so the observation cannot
 * differ.
 *
 * That makes this job's unsat weaker evidence than it looks, and it is worth
 * being explicit about why: here Obs is DEFINED to be R, so the proof
 * establishes that the fixed variant releases nothing BEYOND the sanitizer, and
 * nothing whatsoever about whether the sanitizer itself is safe to release.
 * ckks_unsafe_release_fixed.c says as much -- it calls itself a "structural
 * stand-in" that "does not claim that this establishes a production CKKS
 * noise/circuit-privacy bound". That claim is L4 evidence and is not in scope
 * for any proof in this directory.
 *
 * The unsat is still informative, because the bad harness returns sat under the
 * identical premise and observation: the surplus release is real and this
 * fixture does not make it.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. It also supplies
 * ckks_sanitize_model, the release policy R. */
#include "../../../../compiler_harness/c/ckks_unsafe_release_fixed.c"

extern uint32_t nd_u32(void);

int main(void) {
  uint32_t mask = nd_u32(); /* public inputs, shared by both runs */
  uint32_t cert = nd_u32();

  uint32_t raw0 = nd_u32(); /* run 0 secret */
  uint32_t raw1 = nd_u32(); /* run 1 secret */

  /* R: the authorized release is held EQUAL across the two runs. */
  assume(ckks_sanitize_model(raw0, mask, cert) ==
         ckks_sanitize_model(raw1, mask, cert));

  uint32_t rel0 = 0u, rel1 = 0u;
  ckks_unsafe_release_fixed(raw0, mask, cert, &rel0);
  ckks_unsafe_release_fixed(raw1, mask, cert, &rel1);

  sassert(rel0 == rel1);

  return 0;
}
