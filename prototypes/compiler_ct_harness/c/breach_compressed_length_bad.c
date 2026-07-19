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
 *   none -- this harness uses deterministic public-length padding
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
 *   Models the observable one-byte compression gain when a reflected public
 *   guess matches a secret byte. It is not a compressor or attack client.
 *
 * Secret inputs:
 *   secret_byte
 *
 * Public inputs:
 *   public_guess, encrypted_body, public_wire_length address, and base length
 *
 * Expected confidentiality issue:
 *   Public wire length is 31 on a match and 32 on a mismatch.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -c breach_compressed_length_bad.c
 *
 * License note:
 *   This independently written model contains no BREACH repository code.
 */

#include <stdint.h>

uint32_t breach_compressed_length_bad(uint8_t secret_byte,
                                      uint8_t public_guess,
                                      uint32_t encrypted_body,
                                      uint32_t *public_wire_length) {
  *public_wire_length = 32u - (uint32_t)(secret_byte == public_guess);
  return encrypted_body;
}
