/*
 * Case: secret-dependent dynamic tensor and KV-cache length
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
 *   none -- this harness models public maximum-size padding
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
 *   Models only the observable allocation and work counts associated with a
 *   private sequence length. It does not reproduce vLLM scheduling.
 *
 * Secret inputs:
 *   secret_length
 *
 * Public inputs:
 *   private_result and public observation addresses
 *
 * Expected confidentiality issue:
 *   Allocation size and iteration count directly reveal secret_length.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c dynamic_kv_length_bad.c
 *
 * License note:
 *   This independently written model contains no vLLM source code.
 */

#include <stdint.h>

uint32_t dynamic_kv_length_bad(uint32_t secret_length,
                               uint32_t private_result,
                               uint32_t *public_allocation_count,
                               uint32_t *public_iteration_count) {
  *public_allocation_count = secret_length;
  *public_iteration_count = secret_length;
  return private_result;
}
