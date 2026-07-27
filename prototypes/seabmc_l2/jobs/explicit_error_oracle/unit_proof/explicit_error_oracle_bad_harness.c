/*
 * Unit proof: sequential self-composition of explicit_error_oracle_bad.
 *
 * This is the job that exercises the DECLASSIFICATION premise R of the
 * release-relative property (compiler_harness/mlir/L0_L1_L2_PIPELINE.md):
 *
 *   for all p, s0, s1:
 *     R(p, s0) == R(p, s1)  implies  Obs(Trace(P,p,s0)) == Obs(Trace(P,p,s1))
 *
 * The modelled API deliberately releases one bit -- whether the padding was
 * valid. That release is authorized, so it appears as the PREMISE, not as a
 * violation: the two runs are constrained to agree on it. Anything the observer
 * can still distinguish afterwards exceeds the sanctioned release.
 *
 *   R          = padding_validity_v1 = not(padding_is_valid)   [L0 policy]
 *   Obs        = (*public_status, *public_error_detail, return value)
 *   secrets    = padding_is_valid, padding_error_detail
 *   public     = authorized_plaintext_length (shared by both runs)
 *
 * EXPECTED: sat. The bad variant copies padding_error_detail straight to
 * *public_error_detail, so two runs sharing a validity bit but differing in
 * error detail are still distinguishable -- a padding oracle. The
 * counterexample IS the witness.
 *
 * Unlike secret_embedding_index this job needs no read metadata and no
 * --horn-shadow-mem-load-is-def: the leak is in a value the observer reads
 * directly, so plain output equality suffices.
 *
 * Calibrate against explicit_error_oracle_fixed_harness.c, which must be unsat.
 * A single verdict here means nothing on its own.
 */

#include "seahorn/seahorn.h"

#include <stdint.h>

/* The fixture under test, used in place -- not copied. */
#include "../../../../compiler_harness/c/explicit_error_oracle_bad.c"

extern uint32_t nd_u32(void);

int main(void) {
  uint32_t len = nd_u32(); /* public input, shared by both runs */

  uint32_t v0 = nd_u32(), d0 = nd_u32(); /* run 0 secrets */
  uint32_t v1 = nd_u32(), d1 = nd_u32(); /* run 1 secrets */

  /* Input invariant declared by the fixture: padding_is_valid is a
   * well-formed Boolean. Without it the solver may pick v=2, which is outside
   * the modelled API and would witness a "leak" that cannot occur. */
  assume(v0 <= 1u);
  assume(v1 <= 1u);

  /* R: the authorized release is held EQUAL across the two runs. */
  assume((1u ^ (v0 & 1u)) == (1u ^ (v1 & 1u)));

  uint32_t st0, ed0, st1, ed1;
  uint32_t r0 = explicit_error_oracle_bad(v0, d0, len, &st0, &ed0);
  uint32_t r1 = explicit_error_oracle_bad(v1, d1, len, &st1, &ed1);

  sassert(st0 == st1 && ed0 == ed1 && r0 == r1);

  return 0;
}
