// RUN: %checkpoint-runner run --snapshot fixtures/audience-mismatch/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/audience-mismatch/bad/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/audience-mismatch/bad/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/audience-mismatch/bad/audience_mismatch.bad.mlir --records %t.checkpoints

//
// scope note: the source-boundary stage resolves the AST annotations and the
// case-local policy/ABI. A future exact product replays logit vectors per
// coalition. No compiler-conformance or deployment-evidence claim is made.
// annotation boundary: C annotations and sps.* MLIR references are locators;
// policy owns visibility, ABI owns representation, and neither source nor MLIR
// metadata replaces the frozen NFv2 release carrier.
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
module {
  llvm.func @sps_release_masked_class_candidate(i32) -> i32

  llvm.func @audience_mismatch_bad(
      %logits: i32 {
        sps.component_ref = "logits",
        sps.fixture_refs = ["secret:logits"]},
      %alice_channel: !llvm.ptr {
        sps.abi_root_ref = "alice-channel",
        sps.output_ref = "alice-channel",
        sps.fixture_refs = ["root:alice-channel"]},
      %bob_channel: !llvm.ptr {
        sps.abi_root_ref = "bob-channel",
        sps.fixture_refs = ["public-memory:bob_channel"],
        sps.output_ref = "bob-channel"}) {

    %released = llvm.call @sps_release_masked_class_candidate(%logits)
        {sps.fixture_refs = ["call:masked-class-release"],
         sps.release_ref = "masked-class"} : (i32) -> i32

    // Authorized: alice is the declared audience.
    llvm.store %released, %alice_channel {
      sps.fixture_refs = ["store:alice-channel"],
      sps.output_ref = "alice-channel",
      sps.site_alias = "alice-channel-store"
    } : i32, !llvm.ptr

    // PREFLIGHT FINDING: released value delivered outside its declared audience
    // secret source: %released is derived from concealed %logits by masked-class
    // observable effect: bob_channel receives class indices 3 and 5 for two logit vectors
    // reason: masked-class is outside Bob's audience, so its obligation remains active
    // preflight expectation: unary scanner flags a store outside the candidate release audience
    llvm.store %released, %bob_channel {
      sps.fixture_refs = ["store:bob-channel"],
      sps.output_ref = "bob-channel",
      sps.site_alias = "bob-channel-store"
    } : i32, !llvm.ptr

    llvm.return
  }
}
