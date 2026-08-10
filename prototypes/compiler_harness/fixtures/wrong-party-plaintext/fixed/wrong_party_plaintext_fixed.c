/*
 * Case: wrong-party plaintext delivery (fixed harness)
 *
 * Upstream repository:
 *   none -- this is a compiler-level semantic harness, not copied code
 *
 * Original C source:
 *   none -- the motivating incidents occurred in hosted AI systems
 *
 * Original implementation or report:
 *   https://www.wiz.io/blog/wiz-research-discovers-critical-vulnerability-in-replicate
 *
 * Original fixed code:
 *   none -- this file is the independently written safe counterpart
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
 *   Preserves delivery to the authorized endpoint and transfers only a public
 *   sentinel to the observer endpoint.
 *
 * Secret inputs:
 *   plaintext
 *
 * Public inputs:
 *   endpoint identities, zero sentinel, and party authorization policy
 *
 * Expected confidentiality repair:
 *   No secret-derived value reaches the unauthorized mailbox.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -I../../../include -c wrong_party_plaintext_fixed.c
 *
 * License note:
 *   This independently written reduction contains no upstream source code.
 */

#include <sps/annotations.h>
#include <stdint.h>

extern void sps_transfer_party_authorized(uint32_t value);
extern void sps_transfer_party_observer(uint32_t value);

SPS_ENTRY("wrong_party_plaintext_fixed")
void wrong_party_plaintext_fixed(uint32_t plaintext SPS_COMPONENT("plaintext")) {
  sps_transfer_party_authorized(plaintext);
  sps_transfer_party_observer(0u);
}
