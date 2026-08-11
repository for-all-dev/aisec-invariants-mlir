/*
 * Case: fixed-size array region copy leaks a secret byte
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-acceptance-fixture
 *
 * Relationship to upstream:
 *   Written for this harness. No upstream body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the fixed allocation extent 8 and the public_out target
 *
 * Security intent:
 *   Written for this harness. Both executions allocate the same eight-byte
 *   scratch array. A secret-derived byte is written at offset 0, copied through
 *   offset 4, and then written to the public output root. The local offsets are
 *   internal storage, not independently public regions; the contradiction is
 *   the unequal terminal valueBytes observed at public_out.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm \
 *     alloca_size_fixed_region_copy_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
#include <stdint.h>

SPS_ENTRY("alloca_size_fixed_region_copy_bad")
void alloca_size_fixed_region_copy_bad(
    uint32_t secret SPS_COMPONENT("secret"),
    uint8_t *public_out SPS_ROOT("public-out")) {
  uint8_t scratch[8] = {0};

  scratch[0] = (uint8_t)secret;
  scratch[4] = scratch[0];
  public_out[0] = scratch[4];
}
