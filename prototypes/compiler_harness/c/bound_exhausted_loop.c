/*
 * Case: secret trip-count counterexample and MT-CM2 bound refusal
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
 *   secret_count in bound_secret_trip_count_bad
 *
 * Public inputs:
 *   public_count in bound_exhausted_public_loop, the loop constants, and sink
 *
 * Expected confidentiality issue and refusal:
 *   A secret trip count gives an immediate replayable control counterexample.
 *   The separate public-count function has equal control in both lanes; when a
 *   configured proof bound is too small it produces symmetric BoundExhausted and
 *   therefore Unknown(LoopRemainder), not a counterexample.
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
 * Why these must be separate fixtures:
 *   Counts 0 and 1 diverge at the first branch, before bound exhaustion, so that
 *   case is Counterexample. A reachable, aligned BoundExhausted transition for
 *   the same public count in both lanes yields Unknown with bound adequacy open.
 *
 * Reason-code conflation to avoid:
 *   loop-remainder denotes an exactly modeled reachable BoundExhausted
 *   transition. It must NEVER denote an insufficient engine cap; that is a
 *   resource-limit result. Encoding both with one identifier is a classic
 *   conflation bug, and this fixture exists partly to keep them separable.
 *
 * Note on corpus coverage:
 *   Two earlier fixtures already contain loops with loop-carried block arguments
 *   -- secret_embedding_index.fixed (a 16-iteration public-induction table scan)
 *   and wolfssl_3579_mul.target_fixed (a 64-iteration mask/add multiply) -- so
 *   backedge joins were already exercised. Both have a fixed, public trip count.
 *   What was absent before this file is a backedge whose ITERATION COUNT depends
 *   on a secret, and hence any exercise of bound adequacy.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm bound_exhausted_loop.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
void bound_secret_trip_count_bad(int secret_count, unsigned *public_sink)
{
  int i;

  for (i = 0; i < secret_count; i++) {
    /* Body is deliberately empty: the channel is the backedge count. */
  }

  *public_sink = 0u;
}

void bound_exhausted_public_loop(int public_count, unsigned *public_sink)
{
  int i;

  for (i = 0; i < public_count; i++) {
    /* The bundle deliberately chooses a public count above its proof bound. */
  }

  *public_sink = 0u;
}
