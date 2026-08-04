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
 * before they can stamp read metadata.
 *
 * TWO THINGS HERE ARE LOAD-BEARING AND BOTH LOOK LIKE CLUTTER.
 *
 * 1. `volatile` is required. A volatile store is an observable side effect and
 *    so is not dead code, which is what makes liveness propagate back through
 *    the loads. The pruning that matters happens in `seaopt -O3`, which runs
 *    BEFORE ShadowMem -- delete the loads there and there is no address left to
 *    stamp. Measured, counting `load i32` in the emitted IR:
 *
 *        volatile sink (as written)  ->  2 loads survive
 *        plain (non-volatile) sink   ->  0
 *        no sink at all              ->  0
 *
 *    Drop the `volatile` while tidying and this leaky fixture quietly returns
 *    `unsat` -- a proof that has stopped proving anything, reported as a pass.
 *
 * 2. r0/r1 must be CONSUMED here, never asserted on. Both the bad and the fixed
 *    fixture return table[secret & 15], which legitimately depends on the
 *    secret; `sassert(r0 == r1)` would report a leak on the FIXED fixture. The
 *    observation is the access pattern (f0/f1), not the value.
 *
 * (A later stage, `--horn-bmc-coi=true`, prunes on a different basis and is not
 * a threat to these loads: under --horn-shadow-mem-load-is-def each load
 * produces a memory version that sea_is_read consumes, so they reach the
 * assertion through MEMORY rather than through data.) */
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
