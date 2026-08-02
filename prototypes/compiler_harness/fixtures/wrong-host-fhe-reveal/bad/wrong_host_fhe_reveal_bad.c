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
 *   Models scalar transfers of a reveal result to both an authorized client
 *   and an unauthorized server endpoint. It performs no cryptography.
 *
 * Secret inputs:
 *   revealed_plaintext
 *
 * Public inputs:
 *   ciphertext_handle and the static endpoint contract bindings
 *
 * Expected confidentiality issue:
 *   The server receives plaintext despite lacking reveal authority.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -c wrong_host_fhe_reveal_bad.c
 *
 * License note:
 *   This independently written reduction contains no HEIR source code.
 */

#include <sps/annotations.h>
#include <stdint.h>

extern void sps_transfer_fhe_authorized_client(uint32_t value);
extern void sps_transfer_fhe_server(uint32_t value);

SPS_ENTRY("wrong_host_fhe_reveal_bad")
SPS_RETURN_OUTPUT("return")
uint32_t wrong_host_fhe_reveal_bad(
    uint32_t ciphertext_handle SPS_COMPONENT("ciphertext-handle"),
    uint32_t revealed_plaintext SPS_COMPONENT("revealed-plaintext")) {
  sps_transfer_fhe_authorized_client(revealed_plaintext);
  sps_transfer_fhe_server(revealed_plaintext);
  return ciphertext_handle;
}
