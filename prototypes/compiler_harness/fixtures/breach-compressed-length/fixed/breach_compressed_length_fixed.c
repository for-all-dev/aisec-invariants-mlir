/*
 * Case: BREACH compressed-length disclosure (fixed reduced analogue)
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
 *   Writes the same public length for every secret and guess. It contains no
 *   compressor, padding, or transport event, so it makes no production
 *   mitigation or source-to-runtime correspondence claim.
 *
 * Secret inputs:
 *   secret_byte
 *
 * Public inputs:
 *   public_guess, encrypted_body, public_wire_length address, and the public
 *   constant fixed length 32
 *
 * Expected confidentiality repair:
 *   The reduced model writes public length 32 for every secret and guess.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -I../../../include -c breach_compressed_length_fixed.c
 *
 * License note:
 *   This independently written model contains no BREACH repository code.
 */

#include <sps/annotations.h>
#include <stdint.h>

SPS_ENTRY("breach_compressed_length_fixed")
SPS_RETURN_OUTPUT("return")
uint32_t breach_compressed_length_fixed(
    uint8_t secret_byte SPS_COMPONENT("secret-byte"),
    uint8_t public_guess SPS_COMPONENT("public-guess"),
    uint32_t encrypted_body SPS_COMPONENT("encrypted-body"),
    uint32_t *public_wire_length SPS_ROOT("public-wire-length")) {
  (void)secret_byte;
  (void)public_guess;
  *public_wire_length = 32u;
  return encrypted_body;
}
