/*
 * Case: release carrier binding under optimisation
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   synthetic-minimal-reduction
 *
 * Relationship to upstream:
 *   Not derived from an upstream CVE. This is the C-level origin of the
 *   release-carrier fixture family:
 *   fixtures/release-carrier/pinned-control/release_carrier_pinned.control.mlir,
 *   fixtures/release-carrier/lost-bad/release_carrier_lost.bad.mlir, and
 *   fixtures/release-carrier/marker-only-bad/release_carrier_marker_only.bad.mlir.
 *
 * Secret inputs:
 *   raw
 *
 * Public inputs:
 *   mask_a, mask_b, and the release policy identity "p_invalid_callable"
 *
 * Expected confidentiality issue:
 *   None in this file. The declared release (raw & public_mask) is authorized,
 *   and the wrapper is pinned so the carrier survives.
 *
 * What the fixture family tests:
 *   RETIRED REV4.0/V2 EXPERIMENT. The old profile section 4.4 established a
 *   release identity only through "a direct
 *   call to a manifest-named outlined release wrapper" with a stable SiteId and
 *   ReleaseId, a typed ABI-role mapping, and final call-occurrence cardinality
 *   matching the manifest. None of that is a property of the released VALUE;
 * all of it is a property of where the release SITS. Optimisation is free to
 * move, clone, merge and inline, so the carrier has to be pinned or it is lost.
 *
 *   A CONSTRAINT WORTH KNOWING BEFORE DESIGNING A DECLASSIFIER API. The NF-A08
 *   attribute set is noinline / nomerge / noduplicate / nobuiltin, and it is
 * NOT fully expressible from C. Clang accepts __attribute__((noinline)); it
 * warns and ignores GCC's noclone, and there is no portable C spelling for the
 *   LLVM-level noduplicate. So a release wrapper declared purely in C is pinned
 *   against inlining and nothing else.
 *
 *   The consequence is that the remaining pins must be applied at IR level --
 * by the front end emitting them, or by an SPS pass -- and that a C-only
 *   declaration was therefore an incomplete V2 carrier. SPS-LLVM-NF-v2 does
 *   not repair that wrapper: it replaces it with llvm.sps.release, which this
 *   ordinary C source cannot express. The MLIR fixtures preserve the old
 *   wrapper question only as legacy negative evidence.
 *
 *   Two call sites are present deliberately. With the wrapper pinned there are
 *   two bound occurrences and the manifest can declare multiplicity 2. Without
 *   pinning, both are spliced away and there is nothing to count -- which is
 *   countermodel MT-CM4, global trace order and multiplicity.
 *
 * Canonical compiler command:
 *   clang -std=c11 -I../../../include -O2 --target=x86_64-unknown-linux-gnu -S -emit-llvm \
 *     release_carrier.c
 *
 * License note:
 *   Written for this harness; no upstream code is reproduced.
 */
#include <sps/annotations.h>
typedef unsigned int uint32_t;

SPS_HELPER("invalid-callable")
__attribute__((noinline)) uint32_t
sps_release_invalid_callable(uint32_t raw, uint32_t public_mask) {
  return raw & public_mask;
}

SPS_ENTRY("release_carrier_pinned_control")
void release_carrier(uint32_t raw SPS_COMPONENT("raw"),
                     uint32_t mask_a SPS_COMPONENT("mask-a"),
                     uint32_t mask_b SPS_COMPONENT("mask-b"),
                     uint32_t *sink SPS_ROOT("sink")) {
  sink[0] = sps_release_invalid_callable(raw, mask_a);
  sink[1] = sps_release_invalid_callable(raw, mask_b);
}
