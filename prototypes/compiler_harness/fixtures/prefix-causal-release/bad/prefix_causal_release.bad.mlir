// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic orders the observation before the release carrier; exact product
// replays two secrets whose authorized releases agree while the step-1 channel
// words differ. No compiler-conformance evidence or deployment evidence claim.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// Countermodel MT-CM3, which refutes the invalid principle "a future release may
// condition an earlier observation".
//
// The secret reaches a public channel at step 1, and only afterwards reaches the
// authorized release wrapper at step 2. An end-of-run relation that requires
// equal COMPLETE release histories compares only lanes with equal secret, so it
// declares the step-1 outputs equal and misses this leak entirely.
//
// The rev-4 ledger is prefix-causal: the release transition has no parameter
// through which a future release can affect an earlier step, so the artifact is
// rejected at step 1. LowEq^0 likewise never conditions a pair on equality of a
// FUTURE release.
//
// DATA-STRUCTURE CONSEQUENCE, which is why this two-op fixture is worth its
// keep: the release ledger must be a prefix-indexed SEQUENCE consulted at each
// aligned step, not a whole-run equality installed at query setup. An
// implementation that installs release equality as an initial whole-run
// constraint reports this artifact safe.
//
// Distinct from fixtures/ckks-release/bad/ckks_unsafe_release.bad.mlir, which covers
// an UNAUTHORIZED release. Here the release is entirely legitimate; the defect
// is that it occurs after the observation it would be used to excuse.
//
// CHECK-LABEL: llvm.func @prefix_causal_release_bad
// CHECK-SAME: {{.*}}sps.component_ref = "secret"
// CHECK-SAME: sps.fixture_refs = ["secret:secret"]
// CHECK-SAME: sps.label = "high"
// CHECK-SAME: {{.*}}sps.fixture_refs = ["public-memory:public_channel"]
// CHECK: llvm.store %[[SECRET:.*]], %{{.*}} {sps.fixture_refs = ["store:pre-release-observation"], sps.label = "high", sps.sink_class = "public", sps.site_alias = "pre-release-observation"}
// CHECK: llvm.call @sps_release_policy_h_candidate(%[[SECRET]]) {sps.fixture_refs = ["call:later-release"], sps.release_ref = "policy_h_candidate", sps.site_alias = "later-release-call"}
module {
  llvm.func @sps_release_policy_h_candidate(i32) -> i32

  llvm.func @prefix_causal_release_bad(
      %secret: i32 {
        sps.component_ref = "secret",
        sps.fixture_refs = ["secret:secret"],
        sps.label = "high"},
      %public_channel: !llvm.ptr {
        sps.fixture_refs = ["public-memory:public_channel"],
        sps.output_ref = "public-channel",
        sps.sink_class = "public"}) {
    // PREFLIGHT FINDING: secret observed before its authorized release
    // secret source: %secret reaches the public channel at step 1
    // observable effect: the public channel word differs between two secrets
    // reason: the prefix-causal ledger cannot let a later release excuse step 1
    // preflight expectation: preflight diagnostic prefix-ordered release ledger over the entry
    llvm.store %secret, %public_channel {
      sps.fixture_refs = ["store:pre-release-observation"],
      sps.label = "high",
      sps.sink_class = "public",
      sps.site_alias = "pre-release-observation"
    } : i32, !llvm.ptr
    %released = llvm.call @sps_release_policy_h_candidate(%secret) {
      sps.fixture_refs = ["call:later-release"],
      sps.release_ref = "policy_h_candidate",
      sps.site_alias = "later-release-call"
    } : (i32) -> i32
    llvm.return
  }
}
