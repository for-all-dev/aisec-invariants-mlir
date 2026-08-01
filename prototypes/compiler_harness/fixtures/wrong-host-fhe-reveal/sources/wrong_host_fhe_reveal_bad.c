/*
 * Case: wrong-host FHE reveal
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
 *   none -- the paired file is an independently written policy repair
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
 *   Models a reveal result being placed in both client and unauthorized
 *   server mailboxes. It performs no cryptography.
 *
 * Secret inputs:
 *   revealed_plaintext
 *
 * Public inputs:
 *   ciphertext_handle and mailbox addresses
 *
 * Expected confidentiality issue:
 *   The server receives plaintext despite lacking reveal authority.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c wrong_host_fhe_reveal_bad.c
 *
 * License note:
 *   This independently written reduction contains no HEIR source code.
 */

#include <stdint.h>

uint32_t wrong_host_fhe_reveal_bad(uint32_t ciphertext_handle,
                                   uint32_t revealed_plaintext,
                                   uint32_t *authorized_client_plaintext,
                                   uint32_t *unauthorized_server_plaintext) {
  *authorized_client_plaintext = revealed_plaintext;
  *unauthorized_server_plaintext = revealed_plaintext;
  return ciphertext_handle;
}
