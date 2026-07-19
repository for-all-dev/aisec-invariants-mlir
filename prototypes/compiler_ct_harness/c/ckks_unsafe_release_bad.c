/*
 * Case: CKKS release before sanitization and validation
 *
 * Upstream repository:
 *   https://github.com/microsoft/SEAL
 *
 * Original C source:
 *   none -- this is a policy model and not a Microsoft SEAL vulnerability
 *
 * Original implementation or report:
 *   https://github.com/microsoft/SEAL
 *
 * Original fixed code:
 *   none -- the paired file models a certified public release
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
 *   Models only release ordering. It does not implement CKKS or establish a
 *   circuit-privacy/noise theorem.
 *
 * Secret inputs:
 *   raw_approximate_plaintext
 *
 * Public inputs:
 *   certified_public_value, certificate_ok, and public release address
 *
 * Expected confidentiality issue:
 *   Raw approximate plaintext reaches the public sink before validation.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c ckks_unsafe_release_bad.c
 *
 * License note:
 *   This independently written reduction contains no Microsoft SEAL code.
 */

#include <stdint.h>

uint32_t ckks_unsafe_release_bad(uint32_t raw_approximate_plaintext,
                                 uint32_t certified_public_value,
                                 uint32_t certificate_ok,
                                 uint32_t *public_release) {
  (void)certified_public_value;
  (void)certificate_ok;
  *public_release = raw_approximate_plaintext;
  return raw_approximate_plaintext;
}
