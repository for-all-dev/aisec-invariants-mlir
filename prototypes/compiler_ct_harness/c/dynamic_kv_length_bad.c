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
 *   none -- the paired fixture writes constant public count outputs
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
 *   Models two public count outputs associated with a private sequence
 *   length. It contains no allocation, dynamic shape, loop, or scheduler
 *   event; mapping the fields to those real effects is an L4 obligation.
 *
 * Secret inputs:
 *   secret_length and private_result; private_result is returned only through
 *   the private result channel
 *
 * Public inputs:
 *   public count-output addresses; the returned private_result is outside the
 *   modeled public observation boundary
 *
 * Expected confidentiality issue:
 *   Both public count outputs directly reveal secret_length in the reduced
 *   model.
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
