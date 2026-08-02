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
 *   Models scalar transfer only to the authorized client and a public zero
 *   sentinel transfer to the server. It performs no cryptography.
 *
 * Secret inputs:
 *   revealed_plaintext
 *
 * Public inputs:
 *   ciphertext_handle, static endpoint contract bindings, and zero sentinel
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

extern void sps_transfer_fhe_authorized_client(uint32_t value);
extern void sps_transfer_fhe_server(uint32_t value);

SPS_ENTRY("wrong_host_fhe_reveal_fixed")
SPS_RETURN_OUTPUT("return")
uint32_t wrong_host_fhe_reveal_fixed(
    uint32_t ciphertext_handle SPS_COMPONENT("ciphertext-handle"),
    uint32_t revealed_plaintext SPS_COMPONENT("revealed-plaintext")) {
  sps_transfer_fhe_authorized_client(revealed_plaintext);
  sps_transfer_fhe_server(0u);
  return ciphertext_handle;
}
