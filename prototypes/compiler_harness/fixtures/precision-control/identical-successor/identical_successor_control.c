/*
 * Case: identical-successor precision control
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-precision-control
 *
 * Relationship to upstream:
 *   Written for this harness. No upstream body is copied.
 *
 * Secret inputs:
 *   high_condition
 *
 * Public inputs:
 *   public_value and the return output
 *
 * Security intent:
 *   Written for this harness. Both branch edges reach the same continuation and
 * return the same public value. The sibling policy.sps.yaml owns visibility and
 * the sibling abi.sps.yaml owns the concrete carrier, root, and alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm identical_successor_control.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

/*
 * Control 1: identical successor.
 *
 * The branch condition is secret, but both edges target one block, so no
 * coalition-visible control location differs. Under section 11 the "next
 * control locations differ" disjunct cannot fire when the successor set is a
 * singleton.
 */
SPS_ENTRY("identical_successor_control")
SPS_RETURN_OUTPUT("return")
unsigned identical_successor_control(
    int high_condition SPS_COMPONENT("high-condition"),
    unsigned public_value SPS_COMPONENT("public-value")) {
  if (high_condition) {
    /* fallthrough to the single continuation */
  }
  return public_value;
}
