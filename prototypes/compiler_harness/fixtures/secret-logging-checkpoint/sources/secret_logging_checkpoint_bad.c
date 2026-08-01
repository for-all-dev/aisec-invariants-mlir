/*
 * Case: secret logging and checkpoint export
 *
 * Upstream repository:
 *   https://github.com/kubernetes-sigs/secrets-store-csi-driver
 *
 * Original C source:
 *   none -- the motivating vulnerable implementation is written in Go
 *
 * Original implementation or advisory:
 *   https://github.com/kubernetes-sigs/secrets-store-csi-driver/security/advisories/GHSA-g82w-58jf-gcxx
 *
 * Original fixed code:
 *   https://github.com/kubernetes-sigs/secrets-store-csi-driver/commit/dcb2c294be3bc8b792e02b9f03e5078664db0581
 *
 * Upstream symbol:
 *   NodePublishVolume logging path
 *
 * Upstream vulnerable revision:
 *   parent of dcb2c294be3bc8b792e02b9f03e5078664db0581
 *
 * Upstream fixed revision:
 *   dcb2c294be3bc8b792e02b9f03e5078664db0581
 *
 * Reduction classification:
 *   independently-written-equivalent-reduction
 *
 * Relationship to upstream:
 *   Models a secret token written to public log and artifact sinks. The
 *   checkpoint sink is a separate compiler-harness analogue.
 *
 * Secret inputs:
 *   service_account_token
 *
 * Public inputs:
 *   sink addresses and the zero redaction sentinel
 *
 * Expected confidentiality issue:
 *   Public log readers and artifact readers receive the token.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -c secret_logging_checkpoint_bad.c
 *
 * License note:
 *   This independently written reduction contains no upstream Go code.
 */

#include <stdint.h>

void secret_logging_checkpoint_bad(uint32_t service_account_token,
                                   uint32_t *private_state,
                                   uint32_t *public_log,
                                   uint32_t *public_checkpoint) {
  *private_state = service_account_token;
  *public_log = service_account_token;
  *public_checkpoint = service_account_token;
}
