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
 *   release-carrier fixture family: release_carrier_pinned.control.mlir,
 *   release_carrier_lost.bad.mlir, and release_carrier_marker_only.bad.mlir.
 *
 * Secret inputs:
 *   raw
 *
 * Public inputs:
 *   mask_a, mask_b, and the release policy identity "p_v1"
 *
 * Expected confidentiality issue:
 *   None in this file. The declared release (raw & public_mask) is authorized,
 *   and the wrapper is pinned so the carrier survives.
 *
 * What the fixture family tests:
 *   Profile section 4.4 establishes a release identity only through "a direct
 *   call to a manifest-named outlined release wrapper" with a stable SiteId and
 *   ReleaseId, a typed ABI-role mapping, and final call-occurrence cardinality
 *   matching the manifest. None of that is a property of the released VALUE; all
 *   of it is a property of where the release SITS. Optimisation is free to move,
 *   clone, merge and inline, so the carrier has to be pinned or it is lost.
 *
 *   A CONSTRAINT WORTH KNOWING BEFORE DESIGNING A DECLASSIFIER API. The NF-A08
 *   attribute set is noinline / nomerge / noduplicate / nobuiltin, and it is NOT
 *   fully expressible from C. Clang accepts __attribute__((noinline)); it warns
 *   and ignores GCC's noclone, and there is no portable C spelling for the
 *   LLVM-level noduplicate. So a release wrapper declared purely in C is pinned
 *   against inlining and nothing else.
 *
 *   The consequence is that the remaining pins must be applied at IR level -- by
 *   the front end emitting them, or by an SPS pass -- and that a C-only
 *   declaration is therefore an incomplete carrier. The MLIR fixtures pin the
 *   full set; this file pins what C can express, deliberately, so the gap is
 *   visible rather than assumed away.
 *
 *   Two call sites are present deliberately. With the wrapper pinned there are
 *   two bound occurrences and the manifest can declare multiplicity 2. Without
 *   pinning, both are spliced away and there is nothing to count -- which is
 *   countermodel MT-CM4, global trace order and multiplicity.
 *
 * Canonical compiler command:
 *   clang -std=c11 -O2 --target=x86_64-unknown-linux-gnu -S -emit-llvm \
 *     release_carrier.c
 *
 * License note:
 *   Written for this harness; no upstream code is reproduced.
 */
typedef unsigned int uint32_t;

__attribute__((noinline))
uint32_t sps_release_p_v1(uint32_t raw, uint32_t public_mask) {
  return raw & public_mask;
}

void release_carrier(uint32_t raw, uint32_t mask_a, uint32_t mask_b,
                     uint32_t *sink) {
  sink[0] = sps_release_p_v1(raw, mask_a);
  sink[1] = sps_release_p_v1(raw, mask_b);
}
