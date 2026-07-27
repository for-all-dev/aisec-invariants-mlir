/*
 * Unit proof: sequential self-composition of secret_embedding_index_bad.
 *
 * Property (non-interference on the address channel):
 *
 *   for all public p, secrets s0, s1:
 *     Obs_Theta(Trace(P, p, s0)) == Obs_Theta(Trace(P, p, s1))
 *
 * with Obs_Theta = the set of table slots read. No declassification premise is
 * needed here: the returned value is allowed to depend on the secret (both the
 * bad and the fixed variant return table[secret & 15]), so the return value is
 * deliberately NOT part of the observation.
 *
 * Self-composition is sequential: two runs in one main, sharing one public
 * table, with the footprint cleared between them. The secrets are two free
 * nondet values, so the solver picks the witness pair.
 *
 * EXPECTED: sat -- the load address depends on the secret, so a pair
 * s0, s1 with (s0 & 15) != (s1 & 15) gives different footprints. The
 * counterexample IS the leak witness.
 *
 * Calibrate against secret_embedding_index_fixed_harness.c, which must be
 * unsat. A single verdict here is not meaningful on its own: if the loads were
 * optimised away both harnesses would report unsat, which would look exactly
 * like "the bad variant is secure".
 *
 * Run with --horn-shadow-mem-load-is-def (see ../../../README.md).
 */

#include "../env/observation.h"

/* The fixture under test, used in place -- not copied -- so this proof tracks
 * prototypes/compiler_harness/ rather than drifting from it. */
#include "../../../../compiler_harness/c/secret_embedding_index_bad.c"

/* Keeps the loaded values live so the loads are not dead-code eliminated
 * before they can stamp read metadata. */
volatile uint32_t g_keepalive;

int main(void) {
  uint32_t table[TABLE_N];
  uint32_t s0 = nd_u32();
  uint32_t s1 = nd_u32();

  sea_tracking_on();
  memhavoc(table, sizeof(table)); /* public input, shared by both runs */

  clear_footprint(table);
  uint32_t r0 = secret_embedding_index_bad(table, s0);
  uint32_t f0 = read_footprint(table);

  clear_footprint(table);
  uint32_t r1 = secret_embedding_index_bad(table, s1);
  uint32_t f1 = read_footprint(table);

  g_keepalive = r0 ^ r1;

  sassert(f0 == f1);

  sea_tracking_off();
  return 0;
}
