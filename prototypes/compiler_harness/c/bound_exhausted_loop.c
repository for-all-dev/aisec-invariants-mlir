/*
 * Case: MT-CM2 execution-bound filtering is not a pair filter
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-countermodel-encoding
 *
 * Relationship to upstream:
 *   Encodes countermodel MT-CM2 from the SPS Rev-4 metatheory, which refutes
 *   the invalid principle "bounded-run filtering is a sound proof domain". No
 *   upstream body is copied.
 *
 * Secret inputs:
 *   secret_count, which decides the loop trip count
 *
 * Public inputs:
 *   the loop start value 0, the increment 1, and the public sink target
 *
 * Expected confidentiality issue:
 *   The trip count depends on a secret, so the two lanes execute different
 *   numbers of backedges. Operation count is an observer-visible channel even
 *   though the stored value is a public constant.
 *
 *   The unsound shortcut this pins: an implementation that DELETES the execution
 *   exceeding its unrolling guard silently narrows the proof domain and reports
 *   a safe result. Revision 4 leaves both secret values in Admitted;
 *   BoundAdequate_e(T,B) fails because the larger execution exceeds the guard,
 *   and the guarded expansion produces BoundExhausted instead of deleting the
 *   path. Execution-bound adequacy and universal definedness are deliberately
 *   NOT pair filters inside Admitted; they are universal proof obligations.
 *   Filtering an execution after it exhausts a bound, faults, fails, or risks
 *   undefined behavior is forbidden.
 *
 * Why the outcome is unknown and not unsafe:
 *   A reachable, exactly modeled BoundExhausted transition that does not yield a
 *   replayed bad execution is Unknown with the loop-remainder reason and the
 *   bound-adequacy obligation open. It is NOT a counterexample, because no
 *   replayable witness reaching a bad state has been produced.
 *
 * Reason-code conflation to avoid:
 *   loop-remainder denotes an exactly modeled reachable BoundExhausted
 *   transition. It must NEVER denote an insufficient engine cap; that is a
 *   resource-limit result. Encoding both with one identifier is a classic
 *   conflation bug, and this fixture exists partly to keep them separable.
 *
 * Note on corpus coverage:
 *   Before this file the corpus had no loop at all: all 35 fixtures were
 *   straight-line or single-branch, so nothing exercised fixpoint termination,
 *   backedge joins, or bound adequacy.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm bound_exhausted_loop.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
void bound_exhausted_loop(int secret_count, unsigned *public_sink)
{
  int i;

  for (i = 0; i < secret_count; i++) {
    /* Body is deliberately empty: the channel is the backedge count. */
  }

  *public_sink = 0u;
}
