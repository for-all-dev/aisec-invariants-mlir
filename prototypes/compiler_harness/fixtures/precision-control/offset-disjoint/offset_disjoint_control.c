/*
 * Case: offset-disjoint reload precision control
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
 *   secret_byte
 *
 * Public inputs:
 *   public_value, fixed offsets 4 and 8, and the return output
 *
 * Security intent:
 *   Written for this harness. The secret store at byte offset 4 is disjoint
 * from the public byte stored and reloaded at offset 8. The sibling
 * policy.sps.yaml owns visibility and the sibling abi.sps.yaml owns the
 * concrete carrier, root, and alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm offset_disjoint_control.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

/*
 * Control 4: offset-disjoint reload.
 *
 * The secret is stored at byte offset 4 and the public sink is fed only from
 * byte offset 8. Byte-exact offset disjointness decides this. Offsets are
 * deliberately nonzero: a zero index folds away and would erase the shape.
 */
SPS_ENTRY("offset_disjoint_control")
SPS_RETURN_OUTPUT("return")
unsigned
offset_disjoint_control(unsigned char *buffer SPS_ROOT("buffer"),
                        unsigned secret_byte SPS_COMPONENT("secret-byte"),
                        unsigned public_value SPS_COMPONENT("public-value")) {
  buffer[4] = (unsigned char)secret_byte;
  buffer[8] = (unsigned char)public_value;
  return buffer[8];
}
