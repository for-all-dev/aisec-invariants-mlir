/*
 * Calibration counterpart to secret_embedding_index_bad_harness.c: the same
 * self-composition, run against the REPAIRED fixture.
 *
 * EXPECTED: unsat -- the fixed variant reads every table slot and selects with
 * a constant-time mask, so the footprint is all-ones regardless of the secret
 * and the two runs are indistinguishable on the address channel.
 *
 * This is the positive control that makes the bad harness's `sat` meaningful.
 * Both harnesses returning unsat would indicate the loads never stamped read
 * metadata (optimised away, or --horn-shadow-mem-load-is-def not passed), not
 * that the bad variant is secure. Note also that both variants return the SAME
 * secret-dependent value, so only the access pattern separates these verdicts.
 *
 * Run with --horn-shadow-mem-load-is-def (see ../../../README.md).
 */

#include "../env/observation.h"

#include "../../../../compiler_harness/c/secret_embedding_index_fixed.c"

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
  uint32_t r0 = secret_embedding_index_fixed(table, s0);
  uint32_t f0 = read_footprint(table);

  clear_footprint(table);
  uint32_t r1 = secret_embedding_index_fixed(table, s1);
  uint32_t f1 = read_footprint(table);

  g_keepalive = r0 ^ r1;

  sassert(f0 == f1);

  sea_tracking_off();
  return 0;
}
