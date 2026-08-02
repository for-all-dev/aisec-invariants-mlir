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
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -c wrong_host_fhe_reveal_fixed.c
 *
 * License note:
 *   This independently written reduction contains no HEIR source code.
 */

#include <sps/annotations.h>
#include <stdint.h>

SPS_ENTRY("wrong_host_fhe_reveal_fixed")
SPS_RETURN_OUTPUT("return")
uint32_t wrong_host_fhe_reveal_fixed(
    uint32_t ciphertext_handle SPS_COMPONENT("ciphertext-handle"),
    uint32_t revealed_plaintext SPS_COMPONENT("revealed-plaintext"),
    uint32_t *authorized_client_plaintext
        SPS_ROOT("authorized-client-plaintext"),
    uint32_t *unauthorized_server_plaintext
        SPS_ROOT("unauthorized-server-plaintext")) {
  *authorized_client_plaintext = revealed_plaintext;
  *unauthorized_server_plaintext = 0;
  return ciphertext_handle;
}
