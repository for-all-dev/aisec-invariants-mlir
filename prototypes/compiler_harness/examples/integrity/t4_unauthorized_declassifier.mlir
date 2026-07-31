// RUN: %mlir-opt %s | %FileCheck %s
//
// POST-MVP INTEGRITY/ENDORSEMENT EXAMPLE. Rev4 core deliberately has no
// `authorizers` relation and assigns this file no ModelStatus oracle.
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
// Any future verdict for invalid authorizer identity belongs to a separately
// specified robust-declassification/integrity extension. Rev4 can still reject
// an independently malformed ReleaseTable/carrier binding, but not this
// `authorized_by` policy on its own.
//
// CHECK-LABEL: llvm.func @serve_with_auditor
// CHECK: llvm.call @sps_release_masked_class_v1
// CHECK-SAME: sps.authorized_by = "alice"
module attributes {
  sps.principals = ["alice", "auditor"],
  sps.coalitions_maximal = [["alice", "auditor"]],

  sps.visibility = [
    {item = "logits", visible_to = ["alice"]}
  ],

  // Unchanged from t3: only "auditor" may authorize masked_class_v1.
  sps.release_policies = [
    {id = "masked_class_v1", authorizers = ["auditor"], audience = ["alice"],
     function = "mask-low-byte", carrier = "@sps_release_masked_class_v1"}
  ],

  sps.placement = [{func = "@serve_with_auditor", host = "host_eu"}]
} {
  llvm.func @sps_release_masked_class_v1(i32) -> i32

  llvm.func @serve_with_auditor(
      %logits: i32 {sps.label = "high", sps.item = "logits"},
      %alice_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["alice"]},
      %auditor_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["auditor"]}) {

    // THE ONLY DIFFERENCE FROM t3: alice is not an authorizer of masked_class_v1, so
    // this authorization is invalid and no release is established here.
    //
    // CONFIDENTIALITY ERROR: declassification by a principal with no authority
    // secret source: %logits is declared high and is the sole operand of this carrier call
    // observable effect: raw logits 7 and 9 reach alice_channel unchanged and unequal
    // reason: alice is absent from masked_class_v1's authorizers in this integrity sketch
    // detection boundary: L1 compares sps.authorized_by against the manifest; L2 supplies the 7/9 witness
    %released = llvm.call @sps_release_masked_class_v1(%logits)
        {sps.release_id = "masked_class_v1", sps.authorized_by = "alice"} : (i32) -> i32

    // Now unauthorized even for alice: the premise that would have equalized
    // this store never came into existence.
    llvm.store %released, %alice_channel {sps.audience = ["alice"]} : i32, !llvm.ptr

    llvm.store %released, %auditor_channel {sps.audience = ["auditor"]} : i32, !llvm.ptr

    llvm.return
  }
}
