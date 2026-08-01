/*
 * Case: LeftoverLocals residual scratch model
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
 *   none -- GPU vendors own the exact isolation repair
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
 *   Sequentially models one domain leaving a value in scratch storage that a
 *   later domain publishes. It is not a GPU or cross-process reproduction.
 *
 * Secret inputs:
 *   prior_tenant_secret
 *
 * Public inputs:
 *   next_tenant_public_value, scratch address, and public output address
 *
 * Expected confidentiality issue:
 *   The next tenant publishes residual data owned by the prior tenant.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c leftoverlocals_scratch_bad.c
 *
 * License note:
 *   This independently written reduction contains no upstream kernel code.
 */

#include <stdint.h>

uint32_t leftoverlocals_scratch_bad(uint32_t prior_tenant_secret,
                                    uint32_t next_tenant_public_value,
                                    uint32_t *shared_scratch,
                                    uint32_t *next_tenant_output) {
  *shared_scratch = prior_tenant_secret;
  *next_tenant_output = *shared_scratch;
  return next_tenant_public_value;
}
