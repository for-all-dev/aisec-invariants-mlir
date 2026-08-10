// RUN: %checkpoint-runner run --snapshot fixtures/prefix-causal-release/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/prefix-causal-release/bad/prefix_causal_release.bad.mlir --records %t.checkpoints

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
module {
  llvm.func @llvm.sps.release(i32)
  llvm.func @sps_transfer_prefix_public(i32)

  llvm.func @prefix_causal_release_bad(
      %secret: i32 {
        sps.component_ref = "secret",
        sps.fixture_refs = ["secret:secret"],
        sps.label = "high"}) {
    // PREFLIGHT FINDING: secret observed before its authorized release
    // secret source: %secret reaches the public channel at step 1
    // observable effect: the public channel word differs between two secrets
    // reason: the prefix-causal ledger cannot let a later release excuse step 1
    // preflight expectation: preflight diagnostic prefix-ordered release ledger over the entry
    llvm.call @sps_transfer_prefix_public(%secret) {
      sps.contract_ref = "public-transfer",
      sps.fixture_refs = ["transfer:pre-release-observation"],
      sps.transfer_destination = "public-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.call @llvm.sps.release(%secret) {
      sps.fixture_refs = ["release:policy-h"],
      sps.release_ref = "policy-h",
      sps.site_alias = "later-release"
    } : (i32) -> ()
    llvm.return
  }
}
