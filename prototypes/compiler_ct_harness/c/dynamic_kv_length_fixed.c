/*
 * Case: secret-dependent dynamic tensor and KV-cache length (fixed harness)
 *
 * Upstream repository:
 *   https://github.com/vllm-project/vllm
 *
 * Original C source:
 *   none -- vLLM is Python/CUDA and this is not a claimed vLLM defect
 *
 * Original implementation or report:
 *   https://github.com/vllm-project/vllm/issues/16016
 *
 * Original fixed code:
 *   none -- this is a public-bound padding model
 *
 * Upstream symbol:
 *   none
 *
 * Upstream vulnerable revision:
 *   none
 *
 * Upstream fixed revision:
 *   none
 *
 * Reduction classification:
 *   seeded-semantic-harness
 *
 * Relationship to upstream:
 *   Models a fixed public capacity and fixed amount of externally visible
 *   work while preserving the private logical result.
 *
 * Secret inputs:
 *   secret_length
 *
 * Public inputs:
 *   private_result, public maximum 64, and observation addresses
 *
 * Expected confidentiality repair:
 *   Allocation and iteration observations are always the public maximum 64.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c dynamic_kv_length_fixed.c
 *
 * License note:
 *   This independently written model contains no vLLM source code.
 */

#include <stdint.h>

uint32_t dynamic_kv_length_fixed(uint32_t secret_length,
                                 uint32_t private_result,
                                 uint32_t *public_allocation_count,
                                 uint32_t *public_iteration_count) {
  (void)secret_length;
  *public_allocation_count = 64u;
  *public_iteration_count = 64u;
  return private_result;
}
