/*
 * Case: MT-CM5 missing ABI alias topology
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-countermodel-encoding
 *
 * Relationship to upstream:
 *   Written for this harness. No upstream body is copied.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the initialized q value and public-output target; the p/q topology is intentionally omitted
 *
 * Security intent:
 *   Written for this harness. The ABI intentionally leaves the p/q relation
 * incomplete; the required disposition is Unknown(AliasBindingMismatch). The
 * sibling policy.sps.yaml owns visibility and the sibling abi.sps.yaml owns the
 * concrete carrier, root, and alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm abi_alias_missing_binding.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>
SPS_ENTRY("abi_alias_missing_binding")
void abi_alias_missing_binding(
    unsigned secret SPS_COMPONENT("secret"), unsigned *p SPS_ROOT("p"),
    unsigned *q SPS_ROOT("q"),
    unsigned *public_output SPS_ROOT("public-output")) {
  *p = secret;
  *public_output = *q;
}
