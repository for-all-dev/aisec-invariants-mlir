/*
 * Case: BREACH compressed-length disclosure (reduced analogue)
 *
 * Upstream repository:
 *   https://github.com/nealharris/BREACH
 *
 * Original C source:
 *   none -- the repository contains an attack client, not a C target server
 *
 * Original implementation or report:
 *   https://github.com/nealharris/BREACH/tree/71a9fcbe261b50486be88664046c478956dac857
 *
 * Original fixed code:
 *   none -- the paired reduced fixture writes a constant public length
 *
 * Upstream symbol:
 *   none
 *
 * Upstream vulnerable revision:
 *   71a9fcbe261b50486be88664046c478956dac857
 *
 * Upstream fixed revision:
 *   none
 *
 * Reduction classification:
 *   reduced-runtime-model
 *
 * Relationship to upstream:
 *   Inlines an abstract match-to-length relation: the public length is one
 *   byte shorter when a public guess matches a secret byte. It contains no
 *   compressor call or compression event; source-to-runtime compressor
 *   correspondence is outside this reduced fixture's claim.
 *
 * Secret inputs:
 *   secret_byte
 *
 * Public inputs:
 *   public_guess, encrypted_body, public_wire_length address, and the public
 *   constant base length 32
 *
 * Expected confidentiality issue:
 *   The reduced model directly writes public length 31 on a match and 32 on a
 *   mismatch.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -I../../../include -c breach_compressed_length_bad.c
 *
 * License note:
 *   This independently written model contains no BREACH repository code.
 */

#include <sps/annotations.h>
#include <stdint.h>

SPS_ENTRY("breach_compressed_length_bad")
SPS_RETURN_OUTPUT("return")
uint32_t breach_compressed_length_bad(
    uint8_t secret_byte SPS_COMPONENT("secret-byte"),
    uint8_t public_guess SPS_COMPONENT("public-guess"),
    uint32_t encrypted_body SPS_COMPONENT("encrypted-body"),
    uint32_t *public_wire_length SPS_ROOT("public-wire-length")) {
  *public_wire_length = 32u - (uint32_t)(secret_byte == public_guess);
  return encrypted_body;
}
