/*
 * Case: overlapping offset reload anti-control
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
 *   buffer input, public_value, fixed offsets 4 and 8, and the return output
 *
 * Security intent:
 *   This sibling changes only the returned load from public byte 8 to secret
 *   byte 4. The terminal buffer output remains outside the public boundary.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm offset_overlap_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_ENTRY("offset_overlap_bad")
SPS_RETURN_OUTPUT("return")
unsigned offset_overlap_bad(
    unsigned char *buffer SPS_ROOT("buffer"),
    unsigned secret_byte SPS_COMPONENT("secret-byte"),
    unsigned public_value SPS_COMPONENT("public-value")) {
  buffer[4] = (unsigned char)secret_byte;
  buffer[8] = (unsigned char)public_value;
  return buffer[4];
}
