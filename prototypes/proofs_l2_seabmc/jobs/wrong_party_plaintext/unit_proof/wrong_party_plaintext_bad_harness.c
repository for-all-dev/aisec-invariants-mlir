/*
 * Unit proof: sequential self-composition of wrong_party_plaintext_bad.
 *
 *   secrets = plaintext             (differs between the two runs)
 *   Obs     = *unauthorized_mailbox ONLY
 *
 * THE OBSERVATION SCOPE IS THE WHOLE POINT OF THIS JOB. Both fixtures write the
 * plaintext to *authorized_mailbox -- that is the program working correctly,
 * since the authorized party is entitled to it. The attacker here is the
 * unauthorized party, and their view is their own mailbox. Adding
 * *authorized_mailbox to Obs would make the FIXED harness report sat, and that
 * sat would be a false alarm rather than a leak.
 *
 * This is the cleanest illustration in the directory that "who is observing"
 * is part of the property, not a detail of the encoding. Getting it wrong does
 * not produce an error message; it produces a confident wrong answer.
 *
 * EXPECTED: sat. The bad variant copies the plaintext into the unauthorized
 * mailbox, so two runs differing only in plaintext are distinguishable there.
 *
 * Needs no metadata flags -- the leak is in a value the observer reads directly.
 *
 * Calibrate against wrong_party_plaintext_fixed_harness.c, which must be unsat.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/wrong_party_plaintext_bad.c"

extern uint32_t nd_u32(void);

int main(void) {
  uint32_t p0 = nd_u32(); /* run 0 secret */
  uint32_t p1 = nd_u32(); /* run 1 secret */

  uint32_t auth0 = 0u, unauth0 = 0u;
  uint32_t auth1 = 0u, unauth1 = 0u;

  wrong_party_plaintext_bad(p0, &auth0, &unauth0);
  wrong_party_plaintext_bad(p1, &auth1, &unauth1);

  /* auth0/auth1 are deliberately NOT asserted on. See the note above. */
  sassert(unauth0 == unauth1);

  return 0;
}
