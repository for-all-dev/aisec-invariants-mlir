// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic compares each store's audience against the release
// policy; exact product replays two logit vectors per coalition. No compiler-conformance evidence or deployment evidence claim.
//
// THE FIXTURE THAT MOTIVATED THE RECORD SHAPE. One release, two stores whose IR
// differs only in destination, and FOUR different answers depending on who is
// asking.
//
// The {alice} product is safe, while the {bob} product supplies a replayable
// counterexample. ModelStatus is the single artifact-level aggregate, not a
// per-coalition label. The candidate bundle records these future dispositions.
//
// WHY PER-COALITION ROWS ARE NOT OPTIONAL. Authorization is per-audience, so
// whether a release retires a pair's obligation depends on which coalition is
// asking. For a coalition inside the audience, the prefix-causal ledger retires
// the matching obligation. Outside it, the release payload stays concealed and
// the obligation remains active; the later coalition-visible store reaches Bad.
// A checker that evaluates only maximal {alice,bob} still misses {bob} alone.
//
// The empty coalition sees neither principal channel, so its projected payload
// trace is equal. World-level control/site/order still has to stay in lockstep;
// it does here. The joint coalition contains alice, so the release is authorized
// for it. Only {bob} obtains a replayable bad pair.
//
// The future semantic companion test pins the {bob} row. This shape fixture does
// not run an unimplemented SPS pass.
//
// CHECK-LABEL: llvm.func @audience_mismatch_bad
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: llvm.call @sps_release_masked_class_v1
// CHECK: llvm.store %{{.*}}sps.audience = ["alice"]
// CHECK: llvm.store %{{.*}}sps.audience = ["bob"]
module attributes {
  sps.principals = ["alice", "bob"],
  sps.coalitions_maximal = [["alice", "bob"]],
  // Raw logits are not visible to either principal; only the bound release value
  // may be learned by coalitions containing alice.
  sps.visibility = [{item = "logits", visible_to = []}],
  sps.release_policies = [
    {id = "masked_class_v1", audience = ["alice"], function = "mask-low-byte",
     carrier = "@sps_release_masked_class_v1"}
  ],
  sps.placement = [{func = "@audience_mismatch_bad", host = "host_eu"}]
} {
  llvm.func @sps_release_masked_class_v1(i32) -> i32

  llvm.func @audience_mismatch_bad(
      %logits: i32 {sps.label = "high", sps.item = "logits"},
      %alice_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["alice"]},
      %bob_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["bob"]}) {

    %released = llvm.call @sps_release_masked_class_v1(%logits)
        {sps.release_id = "masked_class_v1"} : (i32) -> i32

    // Authorized: alice is the declared audience.
    llvm.store %released, %alice_channel {sps.audience = ["alice"]} : i32, !llvm.ptr

    // PREFLIGHT FINDING: released value delivered outside its declared audience
    // secret source: %released is derived from high %logits by masked_class_v1
    // observable effect: bob_channel receives class indices 3 and 5 for two logit vectors
    // reason: masked_class_v1 is concealed from bob, so its obligation remains active
    // preflight expectation: unary scanner flags a store outside the candidate release audience
    llvm.store %released, %bob_channel {sps.audience = ["bob"]} : i32, !llvm.ptr

    llvm.return
  }
}
