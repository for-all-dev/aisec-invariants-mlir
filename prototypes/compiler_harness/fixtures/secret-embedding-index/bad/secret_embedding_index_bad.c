/*
 * Case: secret-dependent embedding index
 *
 * Upstream repository:
 *   none -- this is a compiler-level tensor information-flow harness
 *
 * Original C source:
 *   none -- no upstream vulnerability is claimed
 *
 * Original implementation or report:
 *   https://github.com/llvm/torch-mlir
 *
 * Original fixed code:
 *   none -- the paired file is an independently written safe scan
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
 *   Models an embedding lookup whose memory address exposes a secret index.
 *   It is not a claimed torch-mlir defect.
 *
 * Secret inputs:
 *   secret_index
 *
 * Public inputs:
 *   table contents and fixed table size 16
 *
 * Expected confidentiality issue:
 *   The selected load address varies with secret_index.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -c secret_embedding_index_bad.c
 *
 * License note:
 *   This independently written reduction contains no upstream source code.
 */

#include <sps/annotations.h>
#include <stdint.h>

SPS_ENTRY("secret_embedding_index_bad")
SPS_RETURN_OUTPUT("return")
uint32_t secret_embedding_index_bad(const uint32_t table[16] SPS_ROOT("table"),
                                    uint32_t secret_index
                                        SPS_COMPONENT("secret-index")) {
  return table[secret_index & 15u];
}
