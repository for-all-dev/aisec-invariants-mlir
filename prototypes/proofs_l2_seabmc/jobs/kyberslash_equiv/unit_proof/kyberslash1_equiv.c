/*
 * Equivalence proof: kyberslash1_poly_tomsg_vulnerable == ..._fixed,
 * over the WHOLE uint16 domain, with no precondition.
 *
 * This is NOT a non-interference proof, and KyberSlash is not provable as one
 * here. The KyberSlash leak is the latency of a variable-time `udiv` on a
 * secret-derived numerator -- a channel SeaBMC's opsem does not model, since a
 * `udiv` touches no memory for the metadata machinery to attach to. See the
 * README section "Why there is no KyberSlash L2 job".
 *
 * What IS provable, and what this file proves, is that the constant-time
 * rewrite preserves the function:
 *
 *   for all c in uint16:  vulnerable(c) == fixed(c)
 *
 * That is the obligation the fix silently incurs and that nothing in the
 * repository discharged. compiler_harness/c/equivalence_driver.c:125-132
 * checks it by enumeration over c in [0, 3329) only, while the parameter is
 * uint16_t -- so 3329..65535 went untested. For THIS pair that turns out not to
 * matter (see below); for kyberslash2 it does.
 *
 * The rewrite is not obviously equal even on paper: the additive constant
 * changes from 1664 to 1665, and `t *= 80635u` overflows uint32 for large c
 * (65535*2 + 1665 = 132735, times 80635 exceeds 2^32). Wraparound is exactly
 * where a hand argument goes wrong, which is why this is worth proving rather
 * than reasoning about.
 *
 * EXPECTED: unsat -- the two agree everywhere, so NO `assume` appears below.
 * A precondition creeping into this file would be a red flag: it would mean
 * the domain-wide claim had quietly weakened.
 *
 * Calibrated by kyberslash2_equiv_full.c, which uses this same harness shape
 * against the kyberslash2 pair and must come back `sat`. That is what shows the
 * shape can detect an inequivalence at all, and hence that this `unsat` is
 * informative rather than degenerate.
 */

#include "seahorn/seahorn.h"

/* The fixtures under test, used in place -- not copied.
 *
 * Both declare their own `uint8_t`/`uint16_t` typedefs. seahorn.h has already
 * pulled in <stdint.h>, so these are redefinitions of a typedef name to the
 * SAME type, which C11 permits (clang defaults to gnu17). Including both halves
 * of the pair in one translation unit is the point: the proof compares them. */
#include "../../../../compiler_harness/c/kyberslash1_poly_tomsg_vulnerable.c"
#include "../../../../compiler_harness/c/kyberslash1_poly_tomsg_fixed.c"

/* An undefined extern is nondeterministic to SeaHorn. There is no nd_u16, so
 * take a u32 and truncate; the uint16_t parameter type does the constraining. */
extern unsigned int nd_u32(void);

int main(void) {
  uint16_t c = (uint16_t)nd_u32();

#ifdef SEA_PROBE
  /* Reachability probe, expected `sat`. Registered automatically by
   * add_equiv_job for every EXPECT unsat claim.
   *
   * An `unsat` is also what a harness produces when its assumed domain is
   * empty, or when the calls were folded to constants and the equality became
   * trivially true. Asserting that the result CAN be 0 rules both out: a model
   * exists, the call really is evaluated, and its value is not pinned. (c = 0
   * gives (1664/3329) & 1 == 0, so a model does exist.) */
  sassert(kyberslash1_poly_tomsg_vulnerable(c) == 0);
#else
  sassert(kyberslash1_poly_tomsg_vulnerable(c) ==
          kyberslash1_poly_tomsg_fixed(c));
#endif

  return 0;
}
