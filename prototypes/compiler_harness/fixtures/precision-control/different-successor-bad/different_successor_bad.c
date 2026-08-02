/*
 * Case: secret-dependent distinct successor anti-control
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
 *   This source is functional provenance for the hand-authored MLIR. Both
 *   paths return the same public value, but modeled immediate successors
 *   differ. Clang -O0 need not reproduce that exact control trace.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm different_successor_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_ENTRY("different_successor_bad")
SPS_RETURN_OUTPUT("return")
unsigned different_successor_bad(
    int high_condition SPS_COMPONENT("high-condition"),
    unsigned public_value SPS_COMPONENT("public-value")) {
  if (high_condition)
    return public_value;
  return public_value;
}
