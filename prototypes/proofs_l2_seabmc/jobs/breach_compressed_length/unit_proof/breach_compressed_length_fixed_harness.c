/*
 * Unit proof: sequential self-composition of breach_compressed_length_fixed.
 *
 *   secrets = secret_byte                     (differs between the two runs)
 *   public  = public_guess, encrypted_body    (shared by both runs)
 *   Obs     = (*public_wire_length, return value)
 *
 * EXPECTED: unsat. The fixed variant writes a constant 32 regardless of whether
 * the guess matched, so the wire length carries no information about the
 * secret byte.
 *
 * This verdict is only informative because the bad harness returns sat under
 * the same observation.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/breach_compressed_length_fixed.c"

extern uint32_t nd_u32(void);

int main(void) {
  uint8_t guess = (uint8_t)nd_u32(); /* public inputs, shared by both runs */
  uint32_t body = nd_u32();

  uint8_t s0 = (uint8_t)nd_u32(); /* run 0 secret */
  uint8_t s1 = (uint8_t)nd_u32(); /* run 1 secret */

  uint32_t len0 = 0u, len1 = 0u;
  uint32_t r0 = breach_compressed_length_fixed(s0, guess, body, &len0);
  uint32_t r1 = breach_compressed_length_fixed(s1, guess, body, &len1);

  sassert(len0 == len1 && r0 == r1);

  return 0;
}
