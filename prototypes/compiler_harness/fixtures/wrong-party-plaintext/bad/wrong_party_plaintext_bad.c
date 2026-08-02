/*
 * Case: wrong-party plaintext delivery
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
 *   none -- the local fixed file is the safe harness counterpart
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
 *   Models the wrong-party disclosure class with two explicit scalar endpoint
 *   transfer contracts.
 *   It is not a reproduction of the linked hosted-system incident.
 *
 * Secret inputs:
 *   plaintext
 *
 * Public inputs:
 *   endpoint identities and party authorization policy
 *
 * Expected confidentiality issue:
 *   The plaintext is copied to the unauthorized party's mailbox.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -I../../../include -c wrong_party_plaintext_bad.c
 *
 * License note:
 *   This independently written reduction contains no upstream source code.
 */

#include <sps/annotations.h>
#include <stdint.h>

extern void sps_transfer_party_authorized(uint32_t value);
extern void sps_transfer_party_observer(uint32_t value);

SPS_ENTRY("wrong_party_plaintext_bad")
void wrong_party_plaintext_bad(uint32_t plaintext SPS_COMPONENT("plaintext")) {
  sps_transfer_party_authorized(plaintext);
  sps_transfer_party_observer(plaintext);
}
