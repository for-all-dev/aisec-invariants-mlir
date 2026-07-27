// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// DESIGN EXAMPLE. Not part of the enforced corpus; see README.md.
//
// BRING-UP GATE. The second RUN fails today with "expected error ... was not
// produced", exactly like the 17 bad fixtures in ../../mlir/. That is the
// intended state: the diagnostic names the stable reason a future analysis must
// emit at the decisive operation, and implementing that analysis is what turns
// this green. It is not a disabled test and must not be marked XFAIL.
//
// T4 -- unauthorized declassifier. PAIRED WITH t3.
//
// The IR here is identical to t3_declassify_only_actor.mlir except for ONE
// attribute value: `sps.authorized_by` names "alice" instead of "auditor", and
// alice is not in the policy's `authorizers` list.
//
// That single character-level difference changes everything. With no valid
// authorization, the call to the release carrier is just a function call. No
// authorized release exists, so nothing equalizes the flow: the raw item reaches
// a principal channel and two distinct secrets produce two distinct observations.
//
// WHY THIS PAIRING MATTERS. It is the cheapest possible demonstration that the
// manifest is a load-bearing INPUT rather than documentation. The two files have
// the same functions, the same operations in the same order, and the same call to
// the same carrier. An implementation that reads the IR and ignores the manifest
// necessarily gives them the same verdict, and is therefore wrong on one of them.
//
// It also pins the difference between two failure modes that are easy to
// conflate:
//   - t3: the release is valid, the DELIVERY is wrong (wrong audience).
//   - t4: the DELIVERY would be fine, but the release was never authorized.
// Different reasons, different repairs. A single "release violation" code would
// lose that.
//
// Outcome note: this is unsafe rather than unknown because a replayable witness
// exists -- two logit values, no authorizing release, two differing stores. Had
// the carrier merely been unrecognizable, the honest result would instead be
// unknown with a release-conformance obligation open.
//
// coalition rows:
//   {}             unsafe    unauthorized-declassifier
//   {alice}        unsafe    unauthorized-declassifier
//   {auditor}      unsafe    unauthorized-declassifier
//   {alice,auditor} unsafe   unauthorized-declassifier
// artifact aggregate: unsafe
//
// CHECK-LABEL: llvm.func @serve_with_auditor
// CHECK: llvm.call @sps_release_argmax_v1
// CHECK-SAME: sps.authorized_by = "alice"
module attributes {
  sps.principals = ["alice", "auditor"],
  sps.coalitions_maximal = [["alice", "auditor"]],

  sps.visibility = [
    {item = "logits", visible_to = ["alice"]}
  ],

  // Unchanged from t3: only "auditor" may authorize argmax_v1.
  sps.release_policies = [
    {id = "argmax_v1", authorizers = ["auditor"], audience = ["alice"],
     function = "argmax", carrier = "@sps_release_argmax_v1"}
  ],

  sps.placement = [{func = "@serve_with_auditor", host = "host_eu"}]
} {
  llvm.func @sps_release_argmax_v1(i32) -> i32

  llvm.func @serve_with_auditor(
      %logits: i32 {sps.label = "high", sps.item = "logits"},
      %alice_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["alice"]},
      %auditor_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["auditor"]}) {

    // THE ONLY DIFFERENCE FROM t3: alice is not an authorizer of argmax_v1, so
    // this authorization is invalid and no release is established here.
    //
    // CONFIDENTIALITY ERROR: declassification by a principal with no authority
    // secret source: %logits is declared high and is the sole operand of this carrier call
    // observable effect: raw logits 7 and 9 reach alice_channel unchanged and unequal
    // reason: alice is absent from argmax_v1's authorizers, so no release is established and nothing retires the pair
    // detection boundary: L1 compares sps.authorized_by against the manifest; L2 supplies the 7/9 witness
    // expected-error @+1 {{unauthorized-declassifier}}
    %released = llvm.call @sps_release_argmax_v1(%logits)
        {sps.release_id = "argmax_v1", sps.authorized_by = "alice"} : (i32) -> i32

    // Now unauthorized even for alice: the premise that would have equalized
    // this store never came into existence.
    llvm.store %released, %alice_channel {sps.audience = ["alice"]} : i32, !llvm.ptr

    llvm.store %released, %auditor_channel {sps.audience = ["auditor"]} : i32, !llvm.ptr

    llvm.return
  }
}
