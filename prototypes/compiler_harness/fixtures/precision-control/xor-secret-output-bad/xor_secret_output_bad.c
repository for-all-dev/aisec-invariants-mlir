/*
 * Case: XOR secret-output anti-control
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-precision-control
 *
 * Relationship to upstream:
 *   Written for this harness. No upstream body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the return output
 *
 * Security intent:
 *   Replacing the second secret operand with zero removes cancellation and
 *   makes the public return equal to the secret.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm xor_secret_output_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_ENTRY("xor_secret_output_bad")
SPS_RETURN_OUTPUT("return")
unsigned xor_secret_output_bad(unsigned secret SPS_COMPONENT("secret")) {
  return secret ^ 0u;
}
