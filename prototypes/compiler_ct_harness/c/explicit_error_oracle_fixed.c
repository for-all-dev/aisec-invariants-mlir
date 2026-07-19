/*
 * Case: explicit PKCS#1 padding error oracle (fixed harness)
 *
 * Upstream repository:
 *   https://github.com/openssl/openssl
 *
 * Original vulnerable code:
 *   https://github.com/openssl/openssl/blob/1ca61aa56090356bbdbb16cf48916fbd9886c78d/crypto/rsa/rsa_pk1.c#L255-L271
 *
 * Original fixed code:
 *   https://github.com/openssl/openssl/blob/7fc67e0a33102aa47bbaa56533eeecb98c0450f7/crypto/rsa/rsa_pk1.c#L321-L418
 *
 * Fix commit:
 *   https://github.com/openssl/openssl/commit/7fc67e0a33102aa47bbaa56533eeecb98c0450f7
 *
 * Upstream symbol:
 *   ossl_rsa_padding_check_PKCS1_type_2
 *
 * Upstream vulnerable revision:
 *   1ca61aa56090356bbdbb16cf48916fbd9886c78d
 *
 * Upstream fixed revision:
 *   7fc67e0a33102aa47bbaa56533eeecb98c0450f7
 *
 * Reduction classification:
 *   independently-written-equivalent-reduction
 *
 * Relationship to upstream:
 *   Models only uniform public status. OpenSSL's real repair selects a
 *   synthetic plaintext and requires a stronger cryptographic contract.
 *
 * Secret inputs:
 *   padding_is_valid
 *
 * Public inputs:
 *   authorized_plaintext_length, public_status address, and success status
 *
 * Expected confidentiality repair:
 *   The public status is identical for valid and invalid secret padding.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -c explicit_error_oracle_fixed.c
 *
 * License note:
 *   This is independent Apache-2.0-compatible harness code; consult OpenSSL's
 *   linked source and license for the original implementation.
 */

#include <stdint.h>

uint32_t explicit_error_oracle_fixed(uint32_t padding_is_valid,
                                     uint32_t authorized_plaintext_length,
                                     uint32_t *public_status) {
  (void)padding_is_valid;
  *public_status = 0;
  return authorized_plaintext_length;
}
