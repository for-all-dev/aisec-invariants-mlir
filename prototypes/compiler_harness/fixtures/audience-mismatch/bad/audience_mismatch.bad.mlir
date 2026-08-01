// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic compares each store's audience against the release
// policy; exact product replays two logit vectors per coalition. No compiler-conformance evidence or deployment evidence claim.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
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
// CHECK-SAME: {{.*}}sps.component_ref = "logits"
// CHECK-SAME: sps.fixture_refs = ["secret:logits"]
// CHECK-SAME: sps.label = "high"
// CHECK-SAME: {{.*}}sps.fixture_refs = ["public-memory:bob_channel"]
// CHECK-SAME: {{.*}}sps.output_ref = "bob-channel"
// CHECK: llvm.call @sps_release_masked_class_candidate
// CHECK-SAME: sps.fixture_refs = ["call:masked-class-release"]
// CHECK-SAME: sps.release_ref = "masked_class_candidate"
// CHECK: llvm.store %{{.*}} {sps.fixture_refs = ["store:alice-channel"], sps.output_ref = "alice-channel", sps.sink_class = "principal", sps.site_alias = "alice-channel-store"}
// CHECK: llvm.store %{{.*}} {sps.fixture_refs = ["store:bob-channel"], sps.label = "high", sps.output_ref = "bob-channel", sps.sink_class = "public", sps.site_alias = "bob-channel-store"}
module {
  llvm.func @sps_release_masked_class_candidate(i32) -> i32

  llvm.func @audience_mismatch_bad(
      %logits: i32 {
        sps.component_ref = "logits",
        sps.fixture_refs = ["secret:logits"],
        sps.label = "high"},
      %alice_channel: !llvm.ptr {
        sps.output_ref = "alice-channel",
        sps.sink_class = "principal"},
      %bob_channel: !llvm.ptr {
        sps.fixture_refs = ["public-memory:bob_channel"],
        sps.output_ref = "bob-channel",
        sps.sink_class = "public"}) {

    %released = llvm.call @sps_release_masked_class_candidate(%logits)
        {sps.fixture_refs = ["call:masked-class-release"],
         sps.release_ref = "masked_class_candidate"} : (i32) -> i32

    // Authorized: alice is the declared audience.
    llvm.store %released, %alice_channel {
      sps.fixture_refs = ["store:alice-channel"],
      sps.output_ref = "alice-channel",
      sps.sink_class = "principal",
      sps.site_alias = "alice-channel-store"
    } : i32, !llvm.ptr

    // PREFLIGHT FINDING: released value delivered outside its declared audience
    // secret source: %released is derived from high %logits by masked_class_candidate
    // observable effect: bob_channel receives class indices 3 and 5 for two logit vectors
    // reason: masked_class_candidate is concealed from bob, so its obligation remains active
    // preflight expectation: unary scanner flags a store outside the candidate release audience
    llvm.store %released, %bob_channel {
      sps.fixture_refs = ["store:bob-channel"],
      sps.label = "high",
      sps.output_ref = "bob-channel",
      sps.sink_class = "public",
      sps.site_alias = "bob-channel-store"
    } : i32, !llvm.ptr

    llvm.return
  }
}
