// RUN: %mlir-opt %s | %FileCheck %s
//
// case: metatheory/MT-CM4-trace-order-and-multiplicity
// entry: release_carrier_lost_bad
// classification: seeded-semantic-harness
// c source: ../c/release_carrier.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Dialect/LLVMIR/roundtrip.mlir
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %raw, declared by sps.label on the argument
// public: %mask_a, %mask_b, and the release policy identity "p_v1"
// diagnostic focus: release-carrier-lost
// evidence boundary: L1 carrier binding only. No ModelStatus claim.
//
// Countermodel MT-CM4, which refutes the invalid principle "a release is
// identified by a policy name attached to the operation that publishes it".
//
// WHAT HAPPENED. The policy declared one release `p_v1` implemented by an
// outlined wrapper. The optimiser inlined the wrapper at both call sites and
// then CSE'd nothing, leaving two bare `llvm.and` computations and two stores
// that each carry the policy string. Reproduce with:
//
//   mlir-opt release_carrier_pinned.control.mlir --inline --cse
//
// on a variant whose wrapper lacks the pinning attributes.
//
// WHY THIS IS A CARRIER DEFECT AND NOT A LEAK. Profile section 4.4 requires a
// release identity to be established by "a direct call to a manifest-named
// outlined release wrapper" with a stable SiteId/ReleaseId, a typed ABI-role
// mapping, and final call-occurrence cardinality matching the manifest. None of
// those survive here. The correct disposition is a refusal
// (Unknown(ReleaseCarrierMismatch)), never a counterexample and never Proved:
// nothing has been proved or disproved about confidentiality, because the
// policy could not be attached to the artifact at all.
//
// TWO THINGS THIS FIXTURE PINS.
//
// 1. OCCURRENCE IDENTITY. The manifest declares multiplicity 1. After inlining
//    there are two indistinguishable release-shaped stores. An implementation
//    that counts static markers reports multiplicity 2; one that counts
//    dynamic occurrences must still tie each to a declared site, and cannot.
//
// 2. THE STRING IS NOT AUTHORITY. Both stores carry
//    sps.release_policy = "p_v1". REL-01 forbids "a unit attribute whose
//    presence alone authorizes a reveal", and section 2.4 closes with
//    "Syntactic identity, function names, metadata, or analysis-time inlining
//    do not establish ReleaseConforms."
//
// Paired anti-control: release_carrier_marker_only.bad.mlir, where the marker
// is present and the computation is NOT the declared release expression.
// Paired control: release_carrier_pinned.control.mlir, which must NOT be
// reported, so that "refuse every inlined module" is not an accepted fix.
//
// CHECK-LABEL: llvm.func @release_carrier_lost_bad
// CHECK-NOT: llvm.call @sps_release_p_v1
// CHECK: llvm.and
// CHECK: llvm.store {{.*}}sps.release_policy = "p_v1"
// CHECK: llvm.and
// CHECK: llvm.store {{.*}}sps.release_policy = "p_v1"
module {
  llvm.func @release_carrier_lost_bad(
      %raw: i32 {sps.label = "high"},
      %mask_a: i32 {sps.label = "low"},
      %mask_b: i32 {sps.label = "low"},
      %sink: !llvm.ptr {sps.sink_class = "public"}) {
    // CONFIDENTIALITY ERROR: release carrier lost to inlining
    // secret source: %raw is High; the declared release is (raw & mask)
    // observable effect: two release-shaped stores with no bound carrier
    // reason: no direct call to the manifest-named outlined release wrapper
    // detection boundary: L1 carrier binding; fails closed, never Proved
    %a = llvm.and %raw, %mask_a : i32
    llvm.store %a, %sink {sps.release_policy = "p_v1"} : i32, !llvm.ptr
    %b = llvm.and %raw, %mask_b : i32
    llvm.store %b, %sink {sps.release_policy = "p_v1"} : i32, !llvm.ptr
    llvm.return
  }
}
