// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic only. No ModelStatus claim.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// RETIRED REV4.0/V2 EXPERIMENT. The outlined wrapper below is not an SPS-LLVM-
// NF-v2 carrier. NFv2 requires llvm.sps.release and therefore rejects this
// store/metadata shape as ReleaseCarrierMismatch independently of the legacy
// extensional-conformance defect it was designed to teach.
//
// PAIRED ANTI-CONTROL for
// fixtures/release-carrier/lost-bad/release_carrier_lost.bad.mlir.
//
// This fixture exists because of how the carrier defect gets "fixed" in
// practice. An engineer meets Unknown(ReleaseCarrierMismatch), does not want to
// disable inlining, and attaches the policy name to the publishing store so the
// binder finds something. The tool goes quiet. Nothing it was checking has been
// restored.
//
// The artifact below is that shape, made unambiguous: the store carries
// sps.release_policy = "p_invalid_callable", and the value it publishes is the RAW SECRET,
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
// 1. INVALID CARRIER. The callable-surrogate experiment used a direct call to a
//    manifest-named outlined wrapper. NFv2 instead requires the intrinsic. A
//    store satisfies neither carrier contract, regardless of the stored value.
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
// CHECK-SAME: sps.fixture_refs = ["snapshot.secret[0]"]
// CHECK-SAME: sps.label = "high"
// CHECK-SAME: sps.fixture_refs = ["snapshot.public[0]"]
// CHECK-SAME: sps.sink_class = "public"
// CHECK-NOT: llvm.call
// CHECK-NOT: llvm.and
// CHECK: llvm.store %arg0, %{{.*}}sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"]
// CHECK-SAME: sps.observable_candidate = ["release-identity"]
// CHECK-SAME: sps.release_policy = "p_invalid_callable"
// CHECK-SAME: sps.sink_class = "public"
module {
  llvm.func @release_carrier_marker_only_bad(
      %raw: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %mask: i32 {sps.label = "low"},
      %sink: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) {
    // PREFLIGHT FINDING: policy marker present, conformance absent
    // secret source: %raw is marked as a candidate secret and is published verbatim
    // observable effect: the full secret reaches a public channel
    // reason: a metadata string never authorizes a reveal (REL-01)
    // preflight expectation: preflight diagnostic carrier binding AND extensional conformance
    llvm.store %raw, %sink
        {sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"],
         sps.observable_candidate = ["release-identity"],
         sps.release_policy = "p_invalid_callable", sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
