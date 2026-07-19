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
 *   Models two constant public count outputs while preserving the private
 *   logical result. It contains no allocation, dynamic shape, loop, or
 *   scheduler event; mapping the fields to those real effects is L4.
 *
 * Secret inputs:
 *   secret_length and private_result; private_result is returned only through
 *   the private result channel
 *
 * Public inputs:
 *   public count-output addresses and the public constant 64; the returned
 *   private_result is outside the modeled public observation boundary
 *
 * Expected confidentiality repair:
 *   Both public count outputs are always the public constant 64 in the
 *   reduced model.
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
