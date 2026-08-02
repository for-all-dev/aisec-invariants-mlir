// RUN: %checkpoint-runner run --snapshot fixtures/ckks-release/fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/ckks-release/fixed/ckks_unsafe_release.fixed.mlir --records %t.checkpoints

//
// input invariant: %certificate_ok is a well-formed Boolean in {0, 1}
// private result: the function return is not in the public observer projection
// scope note: sanitizer-before-release shape only; production CKKS correctness,
// circuit privacy, and integrity are outside this Rev4 model claim
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @ckks_sanitize_model(
      %raw_approximate_plaintext: i32,
      %public_sanitizer_mask: i32,
      %certificate_ok: i32) -> i32 attributes {
    "sps.fixture_refs" = ["site:ckks-sanitizer"],
    "sps.site_alias" = "ckks-sanitizer"
  } {
    %one = llvm.mlir.constant(1 : i32) : i32
    %zero = llvm.mlir.constant(0 : i32) : i32
    %valid = llvm.and %certificate_ok, %one : i32
    %certificate_mask = llvm.sub %zero, %valid : i32
    %masked_plaintext = llvm.and %raw_approximate_plaintext, %public_sanitizer_mask : i32
    %sanitized = llvm.and %masked_plaintext, %certificate_mask : i32
    llvm.return %sanitized : i32
  }

  llvm.func @ckks_unsafe_release_fixed(
      %raw_approximate_plaintext: i32 {
        sps.component_ref = "raw-approximate-plaintext",
        sps.fixture_refs = ["secret:raw_approximate_plaintext"],
        sps.label = "high"},
      %public_sanitizer_mask: i32,
      %certificate_ok: i32,
      %public_release: !llvm.ptr {
        sps.fixture_refs = ["public-memory:public_release"],
        sps.output_ref = "public-release",
        sps.sink_class = "public"}) -> i32 {
    %sanitized = llvm.call @ckks_sanitize_model(
      %raw_approximate_plaintext,
      %public_sanitizer_mask,
      %certificate_ok) : (i32, i32, i32) -> i32
    // PREFLIGHT CONTROL: release exactly the named sanitizer's policy function
    // secret source: %raw_approximate_plaintext enters the declared sanitizer boundary
    // removed observable: the sink receives no raw detail beyond ckks_masked_release_candidate
    // reason: this policy-tagged store consumes %sanitized, not the raw plaintext
    // preflight expectation: preserve sanitizer-before-release ordering for later binding
    llvm.store %sanitized, %public_release {
      "sps.fixture_refs" = ["store:sanitized-public-release"],
      "sps.release_ref" = "ckks_masked_release_candidate",
      "sps.sink_class" = "public",
      "sps.site_alias" = "ckks-public-release"
    } : i32, !llvm.ptr
    llvm.return %raw_approximate_plaintext : i32
  }
}
