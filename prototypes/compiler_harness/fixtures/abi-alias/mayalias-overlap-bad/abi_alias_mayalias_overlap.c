/*
 * Case: MT-CM5 admitted may-alias overlap
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
 *   the initialized q value, public-output target, and admitted may-alias topology
 *
 * Security intent:
 *   Written for this harness. The ABI admits p and q aliasing, including p ==
 * q, so the reload can disclose secret through public-output. The sibling
 * policy.sps.yaml owns visibility and the sibling abi.sps.yaml owns the
 * concrete carrier, root, and alias bindings.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -I../../../include -O0 \
 *     -Xclang -disable-O0-optnone -S -emit-llvm abi_alias_mayalias_overlap.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
#include <sps/annotations.h>

SPS_ENTRY("abi_alias_mayalias_overlap")
void abi_alias_mayalias_overlap(
    unsigned secret SPS_COMPONENT("secret"), unsigned *p SPS_ROOT("p"),
    unsigned *q SPS_ROOT("q"),
    unsigned *public_output SPS_ROOT("public-output")) {
  *p = secret;
  *public_output = *q;
}
