// RUN: %mlir-opt %s | %FileCheck %s
//
// case: CKKS release after modeled sanitization and validation
// classification: seeded-semantic-harness
// c source: ../c/ckks_unsafe_release_fixed.c
// upstream GitHub source: https://github.com/microsoft/SEAL
// upstream revision: none -- this is a policy model, not a Microsoft SEAL defect
// secret: %raw_approximate_plaintext
// public: trusted-integrity sanitizer mask and certificate flag, plus the public-release stored value
// input invariant: %certificate_ok is a well-formed Boolean in {0, 1}
// private result: the function return is not in the public observer projection
// expected outcome: conditional
// observer/model: public-release-sink
// reason id: sanitized-release-requires-evidence
// outstanding obligations: sanitizer-sufficiency,certificate-soundness,release-policy-integrity
// evidence boundary: L1 sanitizer-before-release structure; L4 discharges production sufficiency
//
// CHECK-LABEL: llvm.func @ckks_sanitize_model
// CHECK-SAME: %[[S_RAW:[a-zA-Z0-9_]+]]: i32, %[[S_MASK:[a-zA-Z0-9_]+]]: i32, %[[S_CERT:[a-zA-Z0-9_]+]]: i32
// CHECK-SAME: sps.contract_kind = "sanitizer"
// CHECK-SAME: sps.contract_status = "requires_l4_evidence"
// CHECK-SAME: sps.release_function = "(raw & public_mask) & certificate_mask"
// CHECK-SAME: sps.release_policy = "ckks_masked_release_v1"
// CHECK-SAME: sps.required_integrity = "public_sanitizer_mask:trusted,certificate_ok:trusted"
// CHECK: %[[ONE:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[CERT_BIT:[0-9]+]] = llvm.and %[[S_CERT]], %[[ONE]]
// CHECK: %[[CERT_MASK:[0-9]+]] = llvm.sub %[[ZERO]], %[[CERT_BIT]]
// CHECK: %[[MASKED:[0-9]+]] = llvm.and %[[S_RAW]], %[[S_MASK]]
// CHECK: %[[RELEASED:[0-9]+]] = llvm.and %[[MASKED]], %[[CERT_MASK]]
// CHECK: llvm.return %[[RELEASED]] : i32
// CHECK-LABEL: llvm.func @ckks_unsafe_release_fixed
// CHECK-SAME: %[[RAW:[a-zA-Z0-9_]+]]: i32, %[[MASK:[a-zA-Z0-9_]+]]: i32, %[[CERT:[a-zA-Z0-9_]+]]: i32, %[[SINK:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK-NOT: llvm.store {{.*}}, %[[SINK]]
// CHECK: %[[SANITIZED:[0-9]+]] = llvm.call @ckks_sanitize_model(%[[RAW]], %[[MASK]], %[[CERT]])
// CHECK-NOT: llvm.store {{.*}}, %[[SINK]]
// CHECK: llvm.store %[[SANITIZED]], %[[SINK]]
// CHECK-SAME: sps.release_guard = "public_sanitizer_mask:trusted,certificate_ok:trusted"
// CHECK-SAME: sps.release_policy = "ckks_masked_release_v1"
// CHECK-NOT: llvm.store {{.*}}, %[[SINK]]
// CHECK: llvm.return %[[RAW]] : i32
module {
  llvm.func @ckks_sanitize_model(
      %raw_approximate_plaintext: i32,
      %public_sanitizer_mask: i32,
      %certificate_ok: i32) -> i32 attributes {
    "sps.contract_kind" = "sanitizer",
    "sps.contract_status" = "requires_l4_evidence",
    "sps.release_function" = "(raw & public_mask) & certificate_mask",
    "sps.release_policy" = "ckks_masked_release_v1",
    "sps.required_integrity" = "public_sanitizer_mask:trusted,certificate_ok:trusted"
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
      %raw_approximate_plaintext: i32,
      %public_sanitizer_mask: i32,
      %certificate_ok: i32,
      %public_release: !llvm.ptr) -> i32 {
    %sanitized = llvm.call @ckks_sanitize_model(
      %raw_approximate_plaintext,
      %public_sanitizer_mask,
      %certificate_ok) : (i32, i32, i32) -> i32
    // CONFIDENTIALITY REPAIR: release exactly the named sanitizer's policy function
    // secret source: %raw_approximate_plaintext enters the declared sanitizer boundary
    // removed observable: the sink receives no raw detail beyond ckks_masked_release_v1
    // reason: this policy-tagged store consumes %sanitized, not the raw plaintext
    // detection boundary: L1 checks ordering, L2 checks R equality, and L4 proves sufficiency
    llvm.store %sanitized, %public_release {
      "sps.release_guard" = "public_sanitizer_mask:trusted,certificate_ok:trusted",
      "sps.release_policy" = "ckks_masked_release_v1"
    } : i32, !llvm.ptr
    llvm.return %raw_approximate_plaintext : i32
  }
}
