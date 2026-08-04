/*
 * Unit proof: sequential self-composition of breach_compressed_length_bad.
 *
 * Models BREACH/CRIME: the ciphertext is opaque, but its LENGTH is not, and
 * compression makes that length depend on whether an attacker-chosen guess
 * matched the secret.
 *
 *   secrets = secret_byte                     (differs between the two runs)
 *   public  = public_guess, encrypted_body    (shared by both runs)
 *   Obs     = (*public_wire_length, return value)
 *
 * The return value is the encrypted body, passed through unchanged by both
 * fixtures. It is shared between the runs, so it contributes nothing either
 * way; it is in Obs because the wire observer really does see it, and leaving
 * it out would be modelling a weaker attacker for no reason.
 *
 * public_guess is attacker-CHOSEN but not attacker-varied: it is one value,
 * shared by both runs, and the solver picks it. That is the right model -- the
 * attacker fixes a guess and then observes which of two secrets is in play.
 *
 * EXPECTED: sat. The bad variant writes 32 - (secret_byte == public_guess), so
 * a run where the guess matches and a run where it does not are distinguishable
 * by one byte of length. One bit per query is the whole attack.
 *
 * Needs no metadata flags -- the leak is in a value the observer reads directly.
 *
 * Calibrate against breach_compressed_length_fixed_harness.c, which must be
 * unsat.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/breach_compressed_length_bad.c"

extern uint32_t nd_u32(void);

int main(void) {
  uint8_t guess = (uint8_t)nd_u32(); /* public inputs, shared by both runs */
  uint32_t body = nd_u32();

  uint8_t s0 = (uint8_t)nd_u32(); /* run 0 secret */
  uint8_t s1 = (uint8_t)nd_u32(); /* run 1 secret */

  uint32_t len0 = 0u, len1 = 0u;
  uint32_t r0 = breach_compressed_length_bad(s0, guess, body, &len0);
  uint32_t r1 = breach_compressed_length_bad(s1, guess, body, &len1);

  sassert(len0 == len1 && r0 == r1);

  return 0;
}
