/*
 * Unit proof: sequential self-composition of ckks_unsafe_release_bad.
 *
 * The second DECLASSIFICATION job in this directory, after
 * explicit_error_oracle -- and the more interesting one, because its authorized
 * release is a non-trivial function rather than a single bit:
 *
 *   for all p, s0, s1:
 *     R(p, s0) == R(p, s1)  implies  Obs(Trace(P,p,s0)) == Obs(Trace(P,p,s1))
 *
 *   R       = ckks_sanitize_model(raw, mask, cert)   [L0 policy]
 *   Obs     = *public_release
 *   secrets = raw_approximate_plaintext
 *   public  = public_sanitizer_mask, certificate_ok  (shared by both runs)
 *
 * TWO THINGS HERE ARE EASY TO GET WRONG.
 *
 * 1. The return value is NOT in Obs. Both fixtures return
 *    raw_approximate_plaintext unchanged (see ckks_unsafe_release_fixed.c) --
 *    it is the caller's own plaintext, not something the public observer sees.
 *    Asserting on it would make the FIXED harness report a leak that does not
 *    exist.
 *
 * 2. This harness includes the FIXED fixture as well as the bad one, purely to
 *    get ckks_sanitize_model. That is intentional. R is the sanitizer, and
 *    restating it here by hand would mean the proof checks a policy that can
 *    silently drift from the one the code implements. The two files define
 *    disjoint top-level names, so including both is safe.
 *
 * EXPECTED: sat. The bad variant ignores the sanitizer entirely and publishes
 * the raw approximate plaintext, so two runs whose SANITIZED forms agree are
 * still distinguishable -- exactly the surplus the release policy forbids. The
 * easiest witness is certificate_ok = 0, where R is identically zero and so
 * constrains nothing, but the leak does not depend on that: even with the
 * certificate present, holding `raw & mask` equal leaves the bits outside the
 * mask free, and the bad variant publishes those too.
 *
 * Needs no metadata flags -- the leak is in a value the observer reads directly.
 *
 * Calibrate against ckks_unsafe_release_fixed_harness.c, which must be unsat.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/ckks_unsafe_release_bad.c"
/* Not under test: included only for ckks_sanitize_model, the release policy R.
 * See note 2 above. */
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
  ckks_unsafe_release_bad(raw0, mask, cert, &rel0);
  ckks_unsafe_release_bad(raw1, mask, cert, &rel1);

  sassert(rel0 == rel1);

  return 0;
}
