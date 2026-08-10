/*
 * Case: CKKS release before sanitization and validation
 *
 * Upstream repository:
 *   https://github.com/microsoft/SEAL
 *
 * Original C source:
 *   none -- this is a policy model and not a Microsoft SEAL vulnerability
 *
 * Original implementation or report:
 *   https://github.com/microsoft/SEAL
 *
 * Original fixed code:
 *   none -- the paired file models a certified masked release
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
 *   Models only the public release boundary. It does not implement CKKS or
 *   establish a circuit-privacy/noise theorem. The function return is a
 *   private result and is outside this fixture's public observer projection.
 *
 * Secret inputs:
 *   raw_approximate_plaintext
 *
 * Public inputs:
 *   trusted-integrity public_sanitizer_mask and certificate_ok, plus the
 *   public release address
 *
 * Input invariant:
 *   certificate_ok is a well-formed Boolean in {0, 1}
 *
 * Public observations:
 *   the value written through public_release; the function return is private
 *
 * Expected confidentiality issue:
 *   Raw approximate plaintext reaches the public sink without an approved
 *   sanitizer result or certificate check.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -c ckks_unsafe_release_bad.c
 *
 * License note:
 *   This independently written reduction contains no Microsoft SEAL code.
 */

#include <sps/annotations.h>
#include <stdint.h>

SPS_HELPER("sanitized-release")
static uint32_t ckks_sanitize_model(uint32_t raw_approximate_plaintext,
                                    uint32_t public_sanitizer_mask,
                                    uint32_t certificate_ok) {
  uint32_t approved = 0u - (certificate_ok & 1u);
  return raw_approximate_plaintext & public_sanitizer_mask & approved;
}

SPS_ENTRY("ckks_unsafe_release_bad")
SPS_RETURN_OUTPUT("return")
uint32_t ckks_unsafe_release_bad(
    uint32_t raw_approximate_plaintext
        SPS_COMPONENT("raw-approximate-plaintext"),
    uint32_t public_sanitizer_mask SPS_COMPONENT("public-sanitizer-mask"),
    uint32_t certificate_ok SPS_COMPONENT("certificate-ok"),
    uint32_t *public_release SPS_ROOT("public-release")) {
  uint32_t authorized = ckks_sanitize_model(
      raw_approximate_plaintext, public_sanitizer_mask, certificate_ok);
  (void)authorized;
  *public_release = raw_approximate_plaintext;
  return raw_approximate_plaintext;
}
