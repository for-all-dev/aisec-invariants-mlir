/*
 * Case: public-overwrite precision control
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
 *   Written for this harness. A public value completely overwrites the secret
 * slot before the return observation. The sibling policy.sps.yaml owns
 * visibility and the sibling abi.sps.yaml owns the concrete carrier, root, and
 * alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm overwritten_slot_control.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

/*
 * Control 3: public overwrite before observation.
 *
 * The secret is written to a slot and then fully overwritten by a public value
 * before any load. Only a strong update discharges this statically, and the
 * diagnostic layer is forbidden from performing one.
 */
SPS_ENTRY("overwritten_slot_control")
SPS_RETURN_OUTPUT("return")
unsigned
overwritten_slot_control(unsigned secret SPS_COMPONENT("secret"),
                         unsigned public_value SPS_COMPONENT("public-value")) {
  unsigned slot;
  slot = secret;
  slot = public_value;
  return slot;
}
