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
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c secret_embedding_index_bad.c
 *
 * License note:
 *   This independently written reduction contains no upstream source code.
 */

#include <stdint.h>

uint32_t secret_embedding_index_bad(const uint32_t table[16],
                                    uint32_t secret_index) {
  return table[secret_index & 15u];
}
