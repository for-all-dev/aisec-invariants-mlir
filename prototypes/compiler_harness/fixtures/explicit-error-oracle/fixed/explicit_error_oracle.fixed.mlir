// RUN: %mlir-opt %s | %FileCheck %s
//
// input invariant: %padding_is_valid is a well-formed Boolean in {0, 1}
// scope note: the preflight suppresses detail; the exact product models only
// the sanctioned validity release, not synthetic-plaintext security
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @explicit_error_oracle_fixed
// CHECK-SAME: %[[VALID:[a-zA-Z0-9_]+]]: i32 {sps.component_ref = "padding-is-valid", sps.fixture_refs = ["secret:padding_is_valid"], sps.label = "high"}
// CHECK-SAME: %[[DETAIL:[a-zA-Z0-9_]+]]: i32 {sps.component_ref = "padding-error-detail", sps.fixture_refs = ["secret:padding_error_detail"], sps.label = "high"}
// CHECK-SAME: %[[LENGTH:[a-zA-Z0-9_]+]]: i32,
// CHECK-SAME: %[[STATUS_SINK:[a-zA-Z0-9_]+]]: !llvm.ptr {sps.fixture_refs = ["public-memory:public_status"], sps.output_ref = "public-status", sps.sink_class = "public"}
// CHECK-SAME: %[[DETAIL_SINK:[a-zA-Z0-9_]+]]: !llvm.ptr {sps.fixture_refs = ["public-memory:public_error_detail"], sps.output_ref = "public-error-detail", sps.sink_class = "public"}
// CHECK-NOT: llvm.store {{.*}}, %[[STATUS_SINK]]
// CHECK-NOT: llvm.store {{.*}}, %[[DETAIL_SINK]]
// CHECK: %[[ONE:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[VALID_BIT:[0-9]+]] = llvm.and %[[VALID]], %[[ONE]]
// CHECK: %[[STATUS:[0-9]+]] = llvm.xor %[[VALID_BIT]], %[[ONE]]
// CHECK-NOT: llvm.store {{.*}}, %[[STATUS_SINK]]
// CHECK-NOT: llvm.store {{.*}}, %[[DETAIL_SINK]]
// CHECK: llvm.store %[[STATUS]], %[[STATUS_SINK]] {sps.fixture_refs = ["store:padding-validity-status"], sps.release_ref = "padding_validity_candidate", sps.sink_class = "public", sps.site_alias = "padding-validity-status"}
// CHECK-NOT: llvm.store {{.*}}, %[[STATUS_SINK]]
// CHECK-NOT: llvm.store {{.*}}, %[[DETAIL_SINK]]
// CHECK: llvm.store %[[ZERO]], %[[DETAIL_SINK]] {sps.fixture_refs = ["store:padding-error-detail-redacted"], sps.label = "public", sps.sink_class = "public", sps.site_alias = "padding-error-detail"}
// CHECK-NOT: llvm.store {{.*}}, %[[STATUS_SINK]]
// CHECK-NOT: llvm.store {{.*}}, %[[DETAIL_SINK]]
// CHECK: llvm.return %[[LENGTH]] : i32
module {
  llvm.func @explicit_error_oracle_fixed(
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
    %zero = llvm.mlir.constant(0 : i32) : i32
    %valid_bit = llvm.and %padding_is_valid, %one : i32
    %status = llvm.xor %valid_bit, %one : i32
    // CANDIDATE RELEASE SITE: authorization of the validity bit is sidecar-bound.
    llvm.store %status, %public_status {
      "sps.fixture_refs" = ["store:padding-validity-status"],
      "sps.release_ref" = "padding_validity_candidate",
      "sps.sink_class" = "public",
      "sps.site_alias" = "padding-validity-status"
    } : i32, !llvm.ptr
    // PREFLIGHT CONTROL: replace the unauthorized padding detail with a constant
    // secret source: %padding_error_detail is deliberately absent from the released value
    // safe effect: callers observe error detail 0 for every secret padding failure
    // reason: %zero has no data dependence on %padding_error_detail
    // preflight expectation: unary scanner sees only the fixed public-detail value
    llvm.store %zero, %public_error_detail {
      sps.fixture_refs = ["store:padding-error-detail-redacted"],
      sps.label = "public",
      sps.sink_class = "public",
      sps.site_alias = "padding-error-detail"
    } : i32, !llvm.ptr
    llvm.return %authorized_plaintext_length : i32
  }
}
