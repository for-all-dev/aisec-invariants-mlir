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
 *   Models padding every response to the same public wire length. It is not
 *   a compressor or proof of a production BREACH mitigation.
 *
 * Secret inputs:
 *   secret_byte
 *
 * Public inputs:
 *   public_guess, encrypted_body, public_wire_length address, and fixed length
 *
 * Expected confidentiality repair:
 *   Public wire length is 32 for every secret and guess.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -c breach_compressed_length_fixed.c
 *
 * License note:
 *   This independently written model contains no BREACH repository code.
 */

#include <stdint.h>

uint32_t breach_compressed_length_fixed(uint8_t secret_byte,
                                        uint8_t public_guess,
                                        uint32_t encrypted_body,
                                        uint32_t *public_wire_length) {
  (void)secret_byte;
  (void)public_guess;
  *public_wire_length = 32u;
  return encrypted_body;
}
