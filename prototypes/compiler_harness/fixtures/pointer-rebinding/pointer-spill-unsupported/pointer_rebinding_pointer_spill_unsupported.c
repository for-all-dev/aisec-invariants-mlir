/*
 * Case: pointer-valued stack spill refusal
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-normal-form-refusal-fixture
 *
 * Relationship to upstream:
 *   Written for this harness. No upstream body is copied.
 *
 * Secret inputs:
 *   secret_selector
 *
 * Public inputs:
 *   the initialized left and right bytes
 *
 * Security intent:
 *   The modeled MLIR deliberately preserves a pointer-valued store and load.
 *   Rev4.1 refuses that frozen shape with Unknown(UnsupportedType) before
 *   relational construction.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm pointer_rebinding_pointer_spill_unsupported.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
#include <stdint.h>

SPS_ENTRY("pointer_rebinding_pointer_spill_unsupported")
void pointer_rebinding_pointer_spill_unsupported(
    uint32_t secret_selector SPS_COMPONENT("secret-selector"),
    const uint8_t *left SPS_ROOT("left"),
    const uint8_t *right SPS_ROOT("right"),
    uint8_t *private_result SPS_ROOT("private-result")) {
  const uint8_t *selected = secret_selector ? right : left;
  const uint8_t *slot = selected;
  *private_result = *slot;
}
