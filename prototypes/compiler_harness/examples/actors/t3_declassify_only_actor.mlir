// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// BRING-UP GATE. The second RUN fails today with "expected error ... was not
// produced", exactly like the 17 bad fixtures in ../../mlir/. That is the
// intended state: the diagnostic names the stable reason a future analysis must
// emit at the decisive operation, and implementing that analysis is what turns
// this green. It is not a disabled test and must not be marked XFAIL.
//
// DESIGN EXAMPLE. Not part of the enforced corpus; see README.md.
//
// T3 -- "may declassify, may never read".
//
// This is the direct encoding of the requirement that certain actors can ONLY
// declassify. `auditor` appears in the `authorizers` list of the release policy
// and appears NOWHERE in `sps.visibility`, and is not in the policy's audience.
//
// Two facts must hold simultaneously, and they are what a single
// principal -> clearance-level map cannot express:
//
//   1. The release IS legitimate. The auditor's authorization is valid, so the
//      store to alice is authorized and verified at {alice}.
//   2. The auditor still may not observe the item. Storing the released value
//      into the auditor's own channel is a leak at {auditor}, because
//      authorization authority conveys no read access.
//
// Fact 2 is the one people get wrong. It is tempting to treat "can authorize a
// release of x" as implying "is cleared for x", since the authorizer is trusted
// with the decision. It does not: the auditor is trusted to decide THAT argmax
// may be published, not to see the logits themselves. Signing authority and read
// authority are separate relations.
//
// Note the released value is stored to the auditor here, not the raw item. Even
// the released value is not for them: they are not in the audience.
//
// coalition rows:
//   {}             unsafe    raw-item-not-world-releasable
//   {alice}        verified  authorized-audience
//   {auditor}      unsafe    authorizer-is-not-a-reader
//   {alice,auditor} unsafe   authorizer-is-not-a-reader
// artifact aggregate: unsafe
//
// LIMIT OF THE DIAGNOSTIC ORACLE: the expected-error below pins the {auditor}
// case only. The empty-coalition row carries a different reason at a different
// site, and one directive per operation cannot express a per-coalition reason
// map. See t1 for the same limit stated at length.
//
// CHECK-LABEL: llvm.func @serve_with_auditor
// CHECK: llvm.call @sps_release_argmax_v1
// CHECK-SAME: sps.authorized_by = "auditor"
// CHECK: llvm.store %{{.*}} {sps.audience = ["alice"]}
// CHECK: llvm.store %{{.*}} {sps.audience = ["auditor"]}
module attributes {
  sps.principals = ["alice", "auditor"],
  sps.coalitions_maximal = [["alice", "auditor"]],

  // auditor is absent from every visibility entry. That absence is the ACL.
  sps.visibility = [
    {item = "logits", visible_to = ["alice"]}
  ],

  // auditor is an authorizer but NOT in the audience. These are different sets
  // on purpose; collapsing them is exactly the bug this example guards against.
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

    // Legitimate: auditor is a declared authorizer of argmax_v1.
    %released = llvm.call @sps_release_argmax_v1(%logits)
        {sps.release_id = "argmax_v1", sps.authorized_by = "auditor"} : (i32) -> i32

    // Authorized: alice is the declared audience.
    llvm.store %released, %alice_channel {sps.audience = ["alice"]} : i32, !llvm.ptr

    // Leak at {auditor}. The auditor authorized this release but is neither a
    // reader of the item nor a member of the audience.
    //
    // CONFIDENTIALITY ERROR: authorizer receives a value it has no authority to read
    // secret source: %released is derived from high %logits by argmax_v1
    // observable effect: auditor_channel receives class indices 3 and 5 for two logit vectors
    // reason: auditor authorizes argmax_v1 but appears in no visibility entry and not in its audience
    // detection boundary: L1 separates authorization from visibility; L2 supplies the 3/5 witness at {auditor}
    // expected-error @+1 {{authorizer-is-not-a-reader}}
    llvm.store %released, %auditor_channel {sps.audience = ["auditor"]} : i32, !llvm.ptr

    llvm.return
  }
}
