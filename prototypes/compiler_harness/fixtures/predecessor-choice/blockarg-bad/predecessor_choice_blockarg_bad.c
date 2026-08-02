/*
 * Case: MT-CM6 predecessor-choice leak through a merge block argument
 *
 * Original C source:
 *   none
 *
 * Shape reference (not copied code, and not an incident):
 *   https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Analysis/DataFlow/test-dead-code-analysis.mlir
 *
 * Upstream revision:
 *   173476ea0407cc037134370a651bb71e9f2dac04
 *
 * Reduction classification:
 *   independently-written-countermodel-encoding
 *
 * Relationship to upstream:
 *   Encodes countermodel MT-CM6 from the SPS Rev-4 metatheory, which refutes
 *   the invalid principle "an ordinary SSA slice is closed around a phi node".
 *   The referenced upstream file is a shape reference for the identical-
 *   successor block form only; no upstream body is copied.
 *
 * Secret inputs:
 *   secret_bit
 *
 * Public inputs:
 *   the two arm constants 10 and 20, and the public sink target
 *
 * Expected confidentiality issue:
 *   No secret value flows through any SSA operand. Both arms materialize public
 *   constants. The secret selects WHICH predecessor edge reaches the merge
 *   block, and the merge block argument therefore carries the secret choice. A
 *   dependence relation closed over SSA operand edges sees two constants and
 *   wrongly reports no flow.
 *
 * Why this is the anti-control for the identical-successor precision control:
 *   Measured with mlir-opt 17.0.6, --canonicalize rewrites this diamond into
 *   llvm.cond_br %arg0, ^bb1(%c10), ^bb1(%c20) -- one successor block reached
 *   twice, differing only in the block-argument operands. That is the identical
 *   successor shape of identical_successor_control.c minus the operands. Under
 *   section 11, Bad_A disjuncts 1 through 4 all hold for this form; the leak
 *   lands only on disjunct 5, the differing projected words at the store. So
 *   repairing the identical-successor control with the rule "identical
 *   successors imply no control leak" silently accepts this leak. The two
 *   fixtures must be maintained together.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm predecessor_choice_blockarg_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
SPS_ENTRY("predecessor_choice_blockarg_bad")
SPS_RETURN_OUTPUT("return")
unsigned
predecessor_choice_blockarg_bad(int secret_bit SPS_COMPONENT("secret-bit")) {
  unsigned selected;

  if (secret_bit) {
    selected = 10u;
  } else {
    selected = 20u;
  }

  return selected;
}
