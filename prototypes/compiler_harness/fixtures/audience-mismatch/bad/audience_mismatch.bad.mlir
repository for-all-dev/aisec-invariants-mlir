// RUN: %checkpoint-runner run --snapshot fixtures/audience-mismatch/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/audience-mismatch/bad/audience_mismatch.bad.mlir --records %t.checkpoints

//
// scope note: the source-boundary stage resolves the AST annotations and the
// case-local policy/ABI. A future exact product replays logit vectors per
// coalition. No compiler-conformance or deployment-evidence claim is made.
// annotation boundary: C annotations and sps.* MLIR references are locators;
// policy owns visibility, ABI owns representation, and neither source nor MLIR
// metadata replaces the frozen NFv2 release carrier.
//
// THE FIXTURE THAT MOTIVATED THE RECORD SHAPE. One release, two cross-host
// scalar calls whose IR differs only in destination, and FOUR answers depending on who is
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
  llvm.func @llvm.sps.release(i32)
  llvm.func @sps_transfer_audience_alice(i32)
  llvm.func @sps_transfer_audience_bob(i32)

  llvm.func @audience_mismatch_bad(
      %logits: i32 {
        sps.component_ref = "logits",
        sps.fixture_refs = ["secret:logits"],
        sps.label = "high"}) {
    %mask = llvm.mlir.constant(255 : i32) : i32
    %released = llvm.and %logits, %mask : i32
    llvm.call @llvm.sps.release(%released) {
      sps.fixture_refs = ["release:masked-class"],
      sps.release_ref = "masked-class",
      sps.site_alias = "masked-class"
    } : (i32) -> ()

    // Authorized: alice is the declared audience.
    llvm.call @sps_transfer_audience_alice(%released) {
      sps.contract_ref = "transfer-alice",
      sps.fixture_refs = ["transfer:alice-endpoint"],
      sps.transfer_destination = "alice-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()

    // PREFLIGHT FINDING: released value delivered outside its declared audience
    // secret source: %released is derived from concealed %logits by masked-class
    // observable effect: Bob's endpoint receives class indices 3 and 5 for two logit vectors
    // reason: masked-class is outside Bob's audience, so its obligation remains active
    // preflight expectation: preserve the explicit Bob-destination contract call for exact binding
    llvm.call @sps_transfer_audience_bob(%released) {
      sps.contract_ref = "transfer-bob",
      sps.fixture_refs = ["transfer:bob-endpoint"],
      sps.transfer_destination = "bob-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()

    llvm.return
  }
}
