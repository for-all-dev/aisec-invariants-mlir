/*
 * Case: CKKS release after modeled sanitization and validation
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
 *   none -- this is the independently written structural counterpart
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
 *   Releases only an independently certified public input. L4 must still
 *   prove that a real CKKS sanitizer and certificate are sufficient.
 *
 * Secret inputs:
 *   raw_approximate_plaintext
 *
 * Public inputs:
 *   certified_public_value, certificate_ok, and public release address
 *
 * Expected confidentiality repair:
 *   The public sink receives no value derived from raw plaintext.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c ckks_unsafe_release_fixed.c
 *
 * License note:
 *   This independently written reduction contains no Microsoft SEAL code.
 */

#include <stdint.h>

uint32_t ckks_unsafe_release_fixed(uint32_t raw_approximate_plaintext,
                                   uint32_t certified_public_value,
                                   uint32_t certificate_ok,
                                   uint32_t *public_release) {
  uint32_t approved = 0u - (certificate_ok & 1u);
  *public_release = certified_public_value & approved;
  return raw_approximate_plaintext;
}
