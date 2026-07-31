// RUN: %mlir-opt %s | %FileCheck %s
//
// DESIGN EXAMPLE. Not part of the enforced corpus; see README.md in this
// directory. The coalition rows below are aspirational: no tool reads them yet.
//
// T1 -- audience mismatch, and why coalition verdicts are NOT monotonic.
//
// THIS IS THE CENTREPIECE EXAMPLE. It is the reason the result record has to be
// keyed by (entry, coalition) rather than by a single observer.
//
// One value is released exactly once, under a policy whose declared audience is
// {alice}. It is then stored to two principal channels. The IR of the two stores
// is identical apart from the destination.
//
//   - For coalitions containing alice, the prefix-causal ledger retires the
//     matching obligation at the carrier occurrence.
//   - For {bob}, the carrier payload is concealed, the obligation remains
//     active, and the later Bob-visible store reaches the bad state.
//
// The product is safe at {alice} and has a replayable counterexample at {bob},
// with no containment relation between those coalitions. A checker that evaluates
// only the authored maximal coalition {alice, bob} never visits {bob} alone and
// reports the artifact clean.
//
// This is why the specification forbids deduplicating results from coalition
// monotonicity, and why a report may not omit a derived coalition.
//
// product rows:
//   {}             ProductSafe
//   {alice}        ProductSafe
//   {bob}          ReplayableCounterexample  bob-visible-output-while-obligation-active
//   {alice,bob}    ProductSafe
// future artifact ModelStatus: Counterexample(ReplayableWitness)
//
// The empty coalition observes neither principal channel, while the joint
// coalition contains alice and is covered by the declared audience. The future
// semantic companion therefore needs only the {bob} counterexample row.
//
// CHECK-LABEL: llvm.func @serve_logits
// CHECK: llvm.call @sps_release_masked_class_v1
// CHECK-SAME: sps.authorized_by = "auditor"
// CHECK-SAME: sps.release_id = "masked_class_v1"
// CHECK: llvm.store %{{.*}} {sps.audience = ["alice"]}
// CHECK: llvm.store %{{.*}} {sps.audience = ["bob"]}
module attributes {
  sps.principals = ["alice", "bob", "auditor"],

  // Only the maximal coalition is authored. The derived set is its downward
  // closure: {}, {alice}, {bob}, {alice, bob}. Every member must be checked,
  // including ones absent from this list.
  sps.coalitions_maximal = [["alice", "bob"]],

  sps.visibility = [
    {item = "logits", visible_to = []}
  ],

  // authorizers and audience are deliberately different sets: the auditor may
  // authorize this release but is not one of its recipients.
  sps.release_policies = [
    {id = "masked_class_v1", authorizers = ["auditor"], audience = ["alice"],
     function = "mask-low-byte", carrier = "@sps_release_masked_class_v1"}
  ],

  sps.placement = [{func = "@serve_logits", host = "host_eu"}]
} {
  // The release rides a direct call to a manifest-named outlined carrier, not an
  // attribute on a store. That gives a stable site identity and a countable call
  // occurrence; release identity is not established by a name alone.
  llvm.func @sps_release_masked_class_v1(i32) -> i32

  llvm.func @serve_logits(
      %logits: i32 {sps.label = "high", sps.item = "logits"},
      %alice_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["alice"]},
      %bob_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["bob"]}) {

    %released = llvm.call @sps_release_masked_class_v1(%logits)
        {sps.release_id = "masked_class_v1", sps.authorized_by = "auditor"} : (i32) -> i32

    // Authorized: alice is the declared audience of masked_class_v1.
    llvm.store %released, %alice_channel {sps.audience = ["alice"]} : i32, !llvm.ptr

    // NOT authorized for {bob}. Byte-identical operation, different verdict.
    //
    // CONFIDENTIALITY ERROR: released value delivered outside its declared audience
    // secret source: %released is derived from high %logits by masked_class_v1
    // observable effect: bob_channel receives class indices 3 and 5 for two logit vectors
    // reason: masked_class_v1 stays concealed from bob, so its obligation remains active
    // detection boundary: L1 compares the store's audience against the release policy; L2 supplies the 3/5 witness
    llvm.store %released, %bob_channel {sps.audience = ["bob"]} : i32, !llvm.ptr

    llvm.return
  }
}
