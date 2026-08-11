/*
 * Case: explicit PKCS#1 padding error oracle
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
 *   RSA_padding_check_PKCS1_type_2
 *
 * Upstream vulnerable revision:
 *   1ca61aa56090356bbdbb16cf48916fbd9886c78d
 *
 * Upstream fixed revision:
 *   7fc67e0a33102aa47bbaa56533eeecb98c0450f7
 *
 * Reduction classification:
 *   seeded-semantic-harness
 *
 * Relationship to upstream:
 *   Models an API where the valid/invalid status is an explicitly sanctioned
 *   release, but a more specific padding diagnostic is not. It does not
 *   implement RSA, padding validation, or OpenSSL's synthetic-plaintext
 *   mechanism.
 *
 * Secret inputs:
 *   padding_is_valid and padding_error_detail
 *
 * Input invariant:
 *   padding_is_valid is a well-formed Boolean in {0, 1}
 *
 * Public inputs:
 *   authorized_plaintext_length, public_status address, and
 *   public_error_detail address
 *
 * Expected confidentiality issue:
 *   The validity bit released through public_status is authorized. The
 *   public_error_detail output additionally distinguishes secret padding
 *   failures that have the same validity bit, so it exceeds that release.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -I../../../include -c explicit_error_oracle_bad.c
 *
 * License note:
 *   This is independent Apache-2.0-compatible harness code; consult OpenSSL's
 *   linked source and license for the original implementation.
 */

#include <sps/annotations.h>
#include <stdint.h>

SPS_HELPER("padding-status")
static uint32_t sps_release_padding_status(uint32_t padding_is_valid) {
  return 1u ^ (padding_is_valid & 1u);
}

SPS_ENTRY("explicit_error_oracle_bad")
SPS_RETURN_OUTPUT("return")
uint32_t explicit_error_oracle_bad(
    uint32_t padding_is_valid SPS_COMPONENT("padding-is-valid"),
    uint32_t padding_error_detail SPS_COMPONENT("padding-error-detail"),
    uint32_t authorized_plaintext_length
        SPS_COMPONENT("authorized-plaintext-length"),
    uint32_t *public_status SPS_ROOT("public-status"),
    uint32_t *public_error_detail SPS_ROOT("public-error-detail")) {
  *public_status = sps_release_padding_status(padding_is_valid);
  *public_error_detail = padding_error_detail;
  return authorized_plaintext_length;
}
