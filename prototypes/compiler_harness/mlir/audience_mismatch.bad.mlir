// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: actor/release-audience-mismatch
// classification: seeded-semantic-harness
// c source: ../c/audience_mismatch_bad.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Dialect/LLVMIR/roundtrip.mlir
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %logits, declared by sps.label on the argument
// public: the argmax release policy and its declared audience
// expected outcome: unsafe
// observer/model: public-sink-value
// reason id: release-audience-mismatch
// outstanding obligations: none
// evidence boundary: L1 compares each store's audience against the release
// policy; L2 replays two logit vectors per coalition. No L3 or L4 claim.
//
// result rows:
//   {}             unsafe    raw-item-not-world-releasable   none
//   {alice}        verified  authorized-audience             none
//   {bob}          unsafe    release-audience-mismatch       none
//   {alice,bob}    unsafe    release-audience-mismatch       none
//
// THE FIXTURE THAT MOTIVATED THE RECORD SHAPE. One release, two stores whose IR
// differs only in destination, and FOUR different answers depending on who is
// asking.
//
// Note the {alice} row: verified, while the artifact aggregate is unsafe. The
// artifact-level outcome is the projection of the rows (unsafe dominates), not
// an independent claim -- and check_harness.py now recomputes it rather than
// trusting the header.
//
// WHY PER-COALITION ROWS ARE NOT OPTIONAL. Authorization is per-audience, so
// whether a release retires a pair's obligation depends on which coalition is
// asking. For a coalition inside the declared audience the differing values are
// permitted and the obligation retires; outside it, nothing retires and the
// identical operation leaks. So verified at one coalition and unsafe at another,
// with NO containment between them: a checker that evaluates only the authored
// maximal coalition {alice,bob} never visits {bob} alone.
//
// The {} row carries a DIFFERENT reason than the {bob} row -- a raw item is not
// world-releasable at all, which is not an audience mismatch. Two reasons at two
// coalitions is precisely what a single reason id could not express, and why
// this scenario lived in examples/actors/ as an unreadable comment until the
// record grew rows.
//
// The expected-error below pins the {bob} case, since one diagnostic per
// operation still cannot carry a per-coalition reason map. That remains a gap;
// it is now a gap in the DIAGNOSTIC surface rather than in the record.
//
// CHECK-LABEL: llvm.func @audience_mismatch_bad
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: llvm.call @sps_release_argmax_v1
// CHECK: llvm.store %{{.*}}sps.audience = ["alice"]
// CHECK: llvm.store %{{.*}}sps.audience = ["bob"]
module attributes {
  sps.principals = ["alice", "bob"],
  sps.coalitions_maximal = [["alice", "bob"]],
  sps.visibility = [{item = "logits", visible_to = ["alice"]}],
  sps.release_policies = [
    {id = "argmax_v1", audience = ["alice"], function = "argmax",
     carrier = "@sps_release_argmax_v1"}
  ],
  sps.placement = [{func = "@audience_mismatch_bad", host = "host_eu"}]
} {
  llvm.func @sps_release_argmax_v1(i32) -> i32

  llvm.func @audience_mismatch_bad(
      %logits: i32 {sps.label = "high", sps.item = "logits"},
      %alice_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["alice"]},
      %bob_channel: !llvm.ptr {sps.sink_class = "principal", sps.audience = ["bob"]}) {

    %released = llvm.call @sps_release_argmax_v1(%logits)
        {sps.release_id = "argmax_v1"} : (i32) -> i32

    // Authorized: alice is the declared audience.
    llvm.store %released, %alice_channel {sps.audience = ["alice"]} : i32, !llvm.ptr

    // CONFIDENTIALITY ERROR: released value delivered outside its declared audience
    // secret source: %released is derived from high %logits by argmax_v1
    // observable effect: bob_channel receives class indices 3 and 5 for two logit vectors
    // reason: argmax_v1 declares audience alice, so nothing retires the obligation at {bob}
    // detection boundary: L1 compares the store audience against the policy; L2 gives the 3/5 witness
    // expected-error @+1 {{release-audience-mismatch}}
    llvm.store %released, %bob_channel {sps.audience = ["bob"]} : i32, !llvm.ptr

    llvm.return
  }
}
