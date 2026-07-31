// RUN: %mlir-opt %s | %FileCheck %s
//
// case: release/carrier-marker-only-anti-control
// entry: release_carrier_marker_only_bad
// classification: seeded-semantic-harness
// c source: ../c/release_carrier.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Dialect/LLVMIR/roundtrip.mlir
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %raw, declared by sps.label on the argument
// public: %mask and the release policy identity "p_v1"
// diagnostic focus: release-marker-without-conformance
// evidence boundary: L1 only. No ModelStatus claim.
//
// PAIRED ANTI-CONTROL for release_carrier_lost.bad.mlir.
//
// This fixture exists because of how the carrier defect gets "fixed" in
// practice. An engineer meets Unknown(ReleaseCarrierMismatch), does not want to
// disable inlining, and attaches the policy name to the publishing store so the
// binder finds something. The tool goes quiet. Nothing it was checking has been
// restored.
//
// The artifact below is that shape, made unambiguous: the store carries
// sps.release_policy = "p_v1", and the value it publishes is the RAW SECRET,
// not the declared release expression (raw & mask). A checker that accepts the
// marker as authorization reports this module safe and publishes the key.
//
// WHY THIS IS THE MOST IMPORTANT FIXTURE IN THE CARRIER FAMILY. The compiler is
// not the adversary here; the workaround is. Carrier loss on its own is loud and
// fails closed. The only route from carrier loss to an unsound result runs
// through a human silencing the refusal. So when auditing an implementation,
// treat a hand-added release marker with far more suspicion than a missing one.
//
// WHAT MUST HOLD. Both of these are independent grounds for refusal, and an
// implementation should be tested for each separately:
//
// 1. CARRIER. Profile section 4.4 requires a direct call to a manifest-named
//    outlined release wrapper. A store is not a call. Fails regardless of the
//    stored value.
//
// 2. CONFORMANCE. ReleaseConforms condition 3 requires the site to emit exactly
//    the deterministic value of the declared expression. Here it emits %raw,
//    and (raw & mask) != raw whenever mask does not cover every set bit of raw.
//    Fails regardless of the carrier.
//
// A checker that reports only one of the two has an incomplete implementation
// even though the verdict happens to be right.
//
// CHECK-LABEL: llvm.func @release_carrier_marker_only_bad
// CHECK-NOT: llvm.call
// CHECK-NOT: llvm.and
// CHECK: llvm.store %arg0, %{{.*}}sps.release_policy = "p_v1"
module {
  llvm.func @release_carrier_marker_only_bad(
      %raw: i32 {sps.label = "high"},
      %mask: i32 {sps.label = "low"},
      %sink: !llvm.ptr {sps.sink_class = "public"}) {
    // CONFIDENTIALITY ERROR: policy marker present, conformance absent
    // secret source: %raw is High and is published verbatim
    // observable effect: the full secret reaches a public channel
    // reason: a metadata string never authorizes a reveal (REL-01)
    // detection boundary: L1 carrier binding AND extensional conformance
    llvm.store %raw, %sink {sps.release_policy = "p_v1"} : i32, !llvm.ptr
    llvm.return
  }
}
