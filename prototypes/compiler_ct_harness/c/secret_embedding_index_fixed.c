/*
 * Case: secret-dependent embedding index (fixed harness)
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
 *   none -- this is the independently written safe counterpart
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
 *   Replaces one secret-addressed load with a public fixed-count scan and
 *   branchless equality masks.
 *
 * Secret inputs:
 *   secret_index
 *
 * Public inputs:
 *   table contents, scan indices, and fixed table size 16
 *
 * Expected confidentiality repair:
 *   Every run loads the same 16 public addresses in the same order.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c secret_embedding_index_fixed.c
 *
 * License note:
 *   This independently written reduction contains no upstream source code.
 */

#include <stdint.h>

static uint32_t embedding_ct_eq_mask(uint32_t a, uint32_t b) {
  uint32_t x = a ^ b;
  x |= 0u - x;
  return 0u - ((x >> 31) ^ 1u);
}

uint32_t secret_embedding_index_fixed(const uint32_t table[16],
                                      uint32_t secret_index) {
  uint32_t selected = 0;
  secret_index &= 15u;
  for (uint32_t i = 0; i < 16; ++i)
    selected |= table[i] & embedding_ct_eq_mask(i, secret_index);
  return selected;
}
