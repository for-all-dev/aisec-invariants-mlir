/*
 * Case: missing public overwrite anti-control
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
 *   secret
 *
 * Public inputs:
 *   public_value and the return output
 *
 * Security intent:
 *   The local slot is observed after its High store because the complete
 *   public overwrite from the paired control is absent.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm missing_overwrite_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_ENTRY("missing_overwrite_bad")
SPS_RETURN_OUTPUT("return")
unsigned missing_overwrite_bad(
    unsigned secret SPS_COMPONENT("secret"),
    unsigned public_value SPS_COMPONENT("public-value")) {
  unsigned slot;
  (void)public_value;
  slot = secret;
  return slot;
}
