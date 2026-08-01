/*
 * Case: wrong-host FHE reveal (fixed harness)
 *
 * Upstream repository:
 *   https://github.com/google/heir
 *
 * Original C source:
 *   none -- this is a placement-policy harness, not a HEIR vulnerability
 *
 * Original implementation or report:
 *   https://github.com/google/heir
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
 *   Models reveal only at the authorized client and a public zero sentinel at
 *   the server. It performs no cryptography.
 *
 * Secret inputs:
 *   revealed_plaintext
 *
 * Public inputs:
 *   ciphertext_handle, mailbox addresses, and zero sentinel
 *
 * Expected confidentiality repair:
 *   Only the authorized client receives the revealed plaintext.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c wrong_host_fhe_reveal_fixed.c
 *
 * License note:
 *   This independently written reduction contains no HEIR source code.
 */

#include <stdint.h>

uint32_t wrong_host_fhe_reveal_fixed(uint32_t ciphertext_handle,
                                     uint32_t revealed_plaintext,
                                     uint32_t *authorized_client_plaintext,
                                     uint32_t *unauthorized_server_plaintext) {
  *authorized_client_plaintext = revealed_plaintext;
  *unauthorized_server_plaintext = 0;
  return ciphertext_handle;
}
