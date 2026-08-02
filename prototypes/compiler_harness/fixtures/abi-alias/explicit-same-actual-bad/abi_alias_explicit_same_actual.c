/*
 * Case: explicit same-actual-pointer alias witness
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-countermodel-encoding
 *
 * Relationship to upstream:
 *   Encodes the explicit same-actual-pointer realization of SPS Rev-4
 *   countermodel MT-CM5. No upstream body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the public output target
 *
 * Expected confidentiality issue:
 *   The wrapper passes one pointer value as both p and q. The helper stores the
 *   secret through p, reloads the same object through q, and copies that value
 *   to public_output. Unlike the independent-ABI-root fixtures, the overlapping
 *   realization is explicit in the call operands themselves.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm abi_alias_explicit_same_actual.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
static void abi_alias_explicit_same_actual_helper(unsigned secret, unsigned *p,
                                                  unsigned *q,
                                                  unsigned *public_output) {
  *p = secret;
  *public_output = *q;
}

SPS_ENTRY("abi_alias_explicit_same_actual")
void abi_alias_explicit_same_actual(unsigned secret SPS_COMPONENT("secret"),
                                    unsigned *shared SPS_ROOT("shared"),
                                    unsigned *public_output
                                        SPS_ROOT("public-output")) {
  abi_alias_explicit_same_actual_helper(secret, shared, shared, public_output);
}
