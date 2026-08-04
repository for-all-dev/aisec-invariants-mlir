/*
 * Unit proof: sequential self-composition of wrong_party_plaintext_fixed.
 *
 *   secrets = plaintext             (differs between the two runs)
 *   Obs     = *unauthorized_mailbox ONLY
 *
 * EXPECTED: unsat. The fixed variant writes a constant 0 to the unauthorized
 * mailbox, so nothing that party sees depends on the plaintext.
 *
 * This fixture still writes the plaintext to *authorized_mailbox, exactly as
 * the bad one does -- which is why *authorized_mailbox must stay out of Obs.
 * Widening the observation to include it would turn this unsat into a sat and
 * the job into a false alarm. See wrong_party_plaintext_bad_harness.c.
 *
 * This verdict is only informative because the bad harness returns sat under
 * the same observation.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/wrong_party_plaintext_fixed.c"

extern uint32_t nd_u32(void);

int main(void) {
  uint32_t p0 = nd_u32(); /* run 0 secret */
  uint32_t p1 = nd_u32(); /* run 1 secret */

  uint32_t auth0 = 0u, unauth0 = 0u;
  uint32_t auth1 = 0u, unauth1 = 0u;

  wrong_party_plaintext_fixed(p0, &auth0, &unauth0);
  wrong_party_plaintext_fixed(p1, &auth1, &unauth1);

  /* auth0/auth1 are deliberately NOT asserted on. See the note above. */
  sassert(unauth0 == unauth1);

  return 0;
}
