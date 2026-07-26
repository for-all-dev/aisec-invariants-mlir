/*
 * Case: diagnostic-precision negative controls
 *
 * Original C source:
 *   none
 *
 * Upstream repository:
 *   https://github.com/llvm/llvm-project
 *
 * Shape reference (not copied code):
 *   https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Analysis/DataFlow/test-dead-code-analysis.mlir
 *
 * Upstream revision:
 *   173476ea0407cc037134370a651bb71e9f2dac04
 *
 * Reduction classification:
 *   independently-written-precision-control
 *
 * Relationship to upstream:
 *   These four functions are written for this harness. They reproduce no
 *   incident and copy no upstream body. Each is a control whose whole purpose
 *   is to pin what the diagnostic analysis is NOT allowed to conclude.
 *
 * Secret inputs:
 *   high_condition, secret, secret_byte
 *
 * Public inputs:
 *   public_value, buffer offsets 4 and 8, and the public sink targets
 *
 * Expected confidentiality issue:
 *   None. Each function is release-relative noninterferent for the named
 *   observer. Under SPS Rev-4 section 10 the single Low/High diagnostic has no
 *   proof-authoritative strong update, no summaries, and no slice selection, so
 *   each of these sites is RelationalRequired at L1 and is decided by the exact
 *   product at L2. The controls exist so that a future SPS analysis which
 *   reports a violation here is detected as imprecise, and so that the
 *   imprecision is never repaired by teaching the diagnostic layer an unsound
 *   strong update or a StaticallyDischarged shortcut.
 *
 * Paired anti-controls:
 *   predecessor_choice_blockarg_bad.c must stay unsafe. Repairing the
 *   identical-successor control below by the rule "identical successors imply
 *   no control leak" silently accepts that anti-control, because
 *   canonicalization reduces it to the same successor shape and the leak lands
 *   only on the differing block-argument operands.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm precision_controls.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */

/*
 * Control 1: identical successor.
 *
 * The branch condition is secret, but both edges target one block, so no
 * coalition-visible control location differs. Under section 11 the "next
 * control locations differ" disjunct cannot fire when the successor set is a
 * singleton.
 */
unsigned identical_successor_control(int high_condition, unsigned public_value)
{
  if (high_condition) {
    /* fallthrough to the single continuation */
  }
  return public_value;
}

/*
 * Control 2: value cancellation.
 *
 * The stored value is secret-derived by dependence but constant in value. A
 * forward Low/High lattice reports High; a value-congruence facility is needed
 * to see that both lanes store zero.
 */
unsigned xor_cancellation_control(unsigned secret)
{
  return secret ^ secret;
}

/*
 * Control 3: public overwrite before observation.
 *
 * The secret is written to a slot and then fully overwritten by a public value
 * before any load. Only a strong update discharges this statically, and the
 * diagnostic layer is forbidden from performing one.
 */
unsigned overwritten_slot_control(unsigned secret, unsigned public_value)
{
  unsigned slot;
  slot = secret;
  slot = public_value;
  return slot;
}

/*
 * Control 4: offset-disjoint reload.
 *
 * The secret is stored at byte offset 4 and the public sink is fed only from
 * byte offset 8. Byte-exact offset disjointness decides this. Offsets are
 * deliberately nonzero: a zero index folds away and would erase the shape.
 */
unsigned offset_disjoint_control(unsigned char *buffer, unsigned secret_byte,
                                 unsigned public_value)
{
  buffer[4] = (unsigned char)secret_byte;
  buffer[8] = (unsigned char)public_value;
  return buffer[8];
}
