/*
 * Case: LeftoverLocals residual scratch model (fixed harness)
 *
 * Upstream repository:
 *   https://github.com/trailofbits/LeftoverLocalsRelease
 *
 * Original C source:
 *   none -- the original proof uses GPU/OpenCL kernels, not portable C
 *
 * Original implementation or report:
 *   https://github.com/trailofbits/LeftoverLocalsRelease
 *
 * Original fixed code:
 *   none -- this file models initialization at a domain transition
 *
 * Upstream symbol:
 *   writer and listener kernels
 *
 * Upstream vulnerable revision:
 *   none
 *
 * Upstream fixed revision:
 *   none
 *
 * Reduction classification:
 *   reduced-runtime-model
 *
 * Relationship to upstream:
 *   Overwrites shared scratch with the next domain's public value before any
 *   read. It is not a proof about real GPU isolation.
 *
 * Secret inputs:
 *   prior_tenant_secret
 *
 * Public inputs:
 *   next_tenant_public_value, scratch address, and public output address
 *
 * Expected confidentiality repair:
 *   The published value no longer depends on prior_tenant_secret.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -c leftoverlocals_scratch_fixed.c
 *
 * License note:
 *   This independently written reduction contains no upstream kernel code.
 */

#include <sps/annotations.h>
#include <stdint.h>

SPS_ENTRY("leftoverlocals_scratch_fixed")
SPS_RETURN_OUTPUT("return")
uint32_t leftoverlocals_scratch_fixed(
    uint32_t prior_tenant_secret SPS_COMPONENT("prior-tenant-secret"),
    uint32_t next_tenant_public_value SPS_COMPONENT("next-tenant-public-value"),
    uint32_t *shared_scratch SPS_ROOT("shared-scratch"),
    uint32_t *next_tenant_output SPS_ROOT("next-tenant-output")) {
  (void)prior_tenant_secret;
  *shared_scratch = next_tenant_public_value;
  *next_tenant_output = *shared_scratch;
  return next_tenant_public_value;
}
