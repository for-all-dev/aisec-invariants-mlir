/*
 * Case: CKKS release after modeled sanitization and validation
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
 *   none -- this is the independently written structural counterpart
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
 *   Models a named sanitizer boundary before the public release. The reduced
 *   release policy authorizes (raw_approximate_plaintext &
 *   public_sanitizer_mask) when certificate_ok is true. L4 must still prove
 *   that a production CKKS sanitizer and certificate are sufficient. The
 *   function return remains private.
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
 * Integrity assumption:
 *   public_sanitizer_mask is fixed by the release-policy authority and
 *   certificate_ok is supplied by its trusted verifier. Neither is selected
 *   by the observer requesting declassification.
 *
 * Public observations:
 *   the value written through public_release; the function return is private
 *
 * Expected confidentiality repair:
 *   A named modeled sanitizer computes exactly the declared release function
 *   before the public sink. Any raw value beyond that release remains private.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -c ckks_unsafe_release_fixed.c
 *
 * License note:
 *   This independently written reduction contains no Microsoft SEAL code.
 */

#include <stdint.h>

/*
 * Structural stand-in for an approved CKKS sanitizer. The reduced harness
 * uses a public bit mask as its declared toy release function; it does not
 * claim that this establishes a production CKKS noise/circuit-privacy bound.
 */
uint32_t ckks_sanitize_model(uint32_t raw_approximate_plaintext,
                             uint32_t public_sanitizer_mask,
                             uint32_t certificate_ok) {
  uint32_t approved = 0u - (certificate_ok & 1u);
  return raw_approximate_plaintext & public_sanitizer_mask & approved;
}

uint32_t ckks_unsafe_release_fixed(uint32_t raw_approximate_plaintext,
                                   uint32_t public_sanitizer_mask,
                                   uint32_t certificate_ok,
                                   uint32_t *public_release) {
  uint32_t sanitized = ckks_sanitize_model(raw_approximate_plaintext,
                                            public_sanitizer_mask,
                                            certificate_ok);
  *public_release = sanitized;
  return raw_approximate_plaintext;
}
