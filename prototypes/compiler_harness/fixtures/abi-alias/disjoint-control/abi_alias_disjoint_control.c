/*
 * Case: proved disjoint ABI alias control
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
 *   the initialized q value, public-output target, and proved-disjoint alias topology
 *
 * Security intent:
 *   Written for this harness. The ABI sidecar proves p, q, and public-output
 * are pairwise disjoint; this is the acceptance twin for MT-CM5. The sibling
 * policy.sps.yaml owns visibility and the sibling abi.sps.yaml owns the
 * concrete carrier, root, and alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm abi_alias_disjoint_control.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_ENTRY("abi_alias_disjoint_control")
void abi_alias_disjoint_control(
    unsigned secret SPS_COMPONENT("secret"), unsigned *p SPS_ROOT("p"),
    unsigned *q SPS_ROOT("q"),
    unsigned *public_output SPS_ROOT("public-output")) {
  *p = secret;
  *public_output = *q;
}
