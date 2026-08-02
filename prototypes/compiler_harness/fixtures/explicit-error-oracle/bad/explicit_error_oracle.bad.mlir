// RUN: %checkpoint-runner run --snapshot fixtures/explicit-error-oracle/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/explicit-error-oracle/bad/explicit_error_oracle.bad.mlir --records %t.checkpoints

//
// input invariant: %padding_is_valid is a well-formed Boolean in {0, 1}
// scope note: preflight diagnostic for the extra detail; exact product holds the sanctioned validity bit fixed
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @explicit_error_oracle_bad(
      %padding_is_valid: i32 {
        sps.component_ref = "padding-is-valid",
        sps.fixture_refs = ["secret:padding_is_valid"],
        sps.label = "high"},
      %padding_error_detail: i32 {
        sps.component_ref = "padding-error-detail",
        sps.fixture_refs = ["secret:padding_error_detail"],
        sps.label = "high"},
      %authorized_plaintext_length: i32,
      %public_status: !llvm.ptr {
        sps.fixture_refs = ["public-memory:public_status"],
        sps.output_ref = "public-status",
        sps.sink_class = "public"},
      %public_error_detail: !llvm.ptr {
        sps.fixture_refs = ["public-memory:public_error_detail"],
        sps.output_ref = "public-error-detail",
        sps.sink_class = "public"}) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %valid_bit = llvm.and %padding_is_valid, %one : i32
    %status = llvm.xor %valid_bit, %one : i32
    // CANDIDATE RELEASE SITE: authorization of the validity bit is sidecar-bound.
    llvm.store %status, %public_status {
      "sps.fixture_refs" = ["store:padding-validity-status"],
      "sps.release_ref" = "padding_validity_candidate",
      "sps.sink_class" = "public",
      "sps.site_alias" = "padding-validity-status"
    } : i32, !llvm.ptr
    // PREFLIGHT FINDING: padding detail exceeds the sanctioned validity release
    // secret source: %padding_error_detail identifies a specific secret padding failure
    // observable effect: a caller reads the secret diagnostic from %public_error_detail
    // reason: equal validity bits with different padding details produce different public outputs
    // preflight expectation: unary scanner flags the unauthorized public-detail store
    llvm.store %padding_error_detail, %public_error_detail {
      sps.fixture_refs = ["store:padding-error-detail"],
      sps.label = "high",
      sps.sink_class = "public",
      sps.site_alias = "padding-error-detail"
    } : i32, !llvm.ptr
    llvm.return %authorized_plaintext_length : i32
  }
}
