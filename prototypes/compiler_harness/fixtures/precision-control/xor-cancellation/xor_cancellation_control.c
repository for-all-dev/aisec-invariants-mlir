/*
 * Case: XOR-cancellation precision control
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
 *   the constant-zero return output
 *
 * Security intent:
 *   Written for this harness. The secret-derived expression is identically zero
 * and is returned on the named output channel. The sibling policy.sps.yaml owns
 * visibility and the sibling abi.sps.yaml owns the concrete carrier, root, and
 * alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm xor_cancellation_control.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

/*
 * Control 2: value cancellation.
 *
 * The stored value is secret-derived by dependence but constant in value. A
 * unary taint abstraction flags the value; a non-authoritative congruence aid
 * can see that both lanes store zero without weakening the exact product.
 */
SPS_ENTRY("xor_cancellation_control")
SPS_RETURN_OUTPUT("return")
unsigned xor_cancellation_control(unsigned secret SPS_COMPONENT("secret")) {
  return secret ^ secret;
}
