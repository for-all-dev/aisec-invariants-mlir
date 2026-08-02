/*
 * Case: secret-dependent pointer rebinding across disjoint allocations
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-address-observation-fixture
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
 *   The selected scalar value can remain equal while the exact allocation
 *   class of the load changes. Policy owns visibility and the ABI sidecar
 *   owns the complete disjoint alias topology.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm pointer_rebinding_disjoint_select_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
#include <stdint.h>

SPS_ENTRY("pointer_rebinding_disjoint_select_bad")
void pointer_rebinding_disjoint_select_bad(
    uint32_t secret_selector SPS_COMPONENT("secret-selector"),
    const uint8_t *left SPS_ROOT("left"),
    const uint8_t *right SPS_ROOT("right"),
    uint8_t *private_result SPS_ROOT("private-result")) {
  const uint8_t *selected = secret_selector ? right : left;
  *private_result = *selected;
}
