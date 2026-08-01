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
 *   Preserves delivery to the authorized mailbox and emits only a public
 *   sentinel to the unauthorized mailbox.
 *
 * Secret inputs:
 *   plaintext
 *
 * Public inputs:
 *   mailbox addresses, zero sentinel, and party authorization policy
 *
 * Expected confidentiality repair:
 *   No secret-derived value reaches the unauthorized mailbox.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -c wrong_party_plaintext_fixed.c
 *
 * License note:
 *   This independently written reduction contains no upstream source code.
 */

#include <stdint.h>

void wrong_party_plaintext_fixed(uint32_t plaintext,
                                 uint32_t *authorized_mailbox,
                                 uint32_t *unauthorized_mailbox) {
  *authorized_mailbox = plaintext;
  *unauthorized_mailbox = 0;
}
