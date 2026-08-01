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
 *   Models the wrong-party disclosure class with two explicit mailboxes.
 *   It is not a reproduction of the linked hosted-system incident.
 *
 * Secret inputs:
 *   plaintext
 *
 * Public inputs:
 *   mailbox addresses and party authorization policy
 *
 * Expected confidentiality issue:
 *   The plaintext is copied to the unauthorized party's mailbox.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -c wrong_party_plaintext_bad.c
 *
 * License note:
 *   This independently written reduction contains no upstream source code.
 */

#include <stdint.h>

void wrong_party_plaintext_bad(uint32_t plaintext,
                               uint32_t *authorized_mailbox,
                               uint32_t *unauthorized_mailbox) {
  *authorized_mailbox = plaintext;
  *unauthorized_mailbox = plaintext;
}
