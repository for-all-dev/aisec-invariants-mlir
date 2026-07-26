/*
 * Case: MT-CM3 observation before an authorized release
 *
 * Original C source:
 *   none
 *
 * Reduction classification:
 *   independently-written-countermodel-encoding
 *
 * Relationship to upstream:
 *   Encodes countermodel MT-CM3 from the SPS Rev-4 metatheory, which refutes
 *   the invalid principle "a future release may condition an earlier
 *   observation". No upstream body is copied and this is not an incident
 *   reduction.
 *
 * Secret inputs:
 *   secret
 *
 * Public inputs:
 *   the public channel target and the release policy identity
 *
 * Expected confidentiality issue:
 *   The secret is written to a public channel at step 1, and only afterwards
 *   passed to the authorized release wrapper at step 2. An end-of-run relation
 *   that requires equal complete release histories compares only lanes with
 *   equal secret, so it declares the step-1 outputs equal and misses the leak
 *   entirely.
 *
 *   The rev-4 ledger is prefix-causal: LedgerStep_A has no parameter through
 *   which a future release can affect an earlier step, so the program is
 *   rejected at step 1. This is also why release equality may not be installed
 *   as a whole-run initial constraint in the SMT query.
 *
 * Why the existing CKKS fixture does not cover this:
 *   ckks_unsafe_release covers an UNAUTHORIZED release. This covers temporal
 *   laundering of an AUTHORIZED one: the release here is legitimate, but it
 *   happens after the observation it is being used to excuse.
 *
 * Data-structure consequence:
 *   The release ledger must be a prefix-indexed sequence consulted at each
 *   aligned step, not a whole-run equality installed at query setup. A fixture
 *   that passes only under the whole-run encoding is the regression this pins.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Wpedantic -O0 -Xclang -disable-O0-optnone \
 *     -S -emit-llvm prefix_causal_release_bad.c
 *
 * License note:
 *   Written for this harness. Contains no third-party source.
 */
/*
 * Modeled release wrapper. Defined here rather than declared extern so that the
 * corpus stays linkable: c/Makefile compiles and links every *.c file into the
 * equivalence driver, so an undefined symbol breaks check-equivalence.
 *
 * The body is deliberately the identity on the authorized projection. What this
 * fixture pins is the ORDER of the observation relative to this call, not the
 * release function's contents.
 */
unsigned sps_release_policy_h_v1(unsigned raw)
{
  return raw;
}

void prefix_causal_release_bad(unsigned secret, unsigned *public_channel)
{
  /* Step 1: the secret is observable here, before any release is performed. */
  *public_channel = secret;

  /* Step 2: the authorized release cannot retroactively excuse step 1. */
  (void)sps_release_policy_h_v1(secret);
}
