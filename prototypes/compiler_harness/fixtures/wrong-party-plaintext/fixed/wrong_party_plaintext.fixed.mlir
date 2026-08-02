// RUN: %checkpoint-runner run --snapshot fixtures/wrong-party-plaintext/fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wrong-party-plaintext/fixed/wrong_party_plaintext.fixed.mlir --records %t.checkpoints

//
// scope note: reduced placement/output-policy shape only; the linked hosted
// incident is not encoded by this fixture
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @sps_transfer_party_authorized(i32)
  llvm.func @sps_transfer_party_observer(i32)

  llvm.func @wrong_party_plaintext_fixed(
      %plaintext: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) {
    llvm.call @sps_transfer_party_authorized(%plaintext) {
      sps.contract_ref = "authorized-transfer",
      sps.transfer_destination = "authorized-mailbox-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    %zero = llvm.mlir.constant(0 : i32) : i32
    // PREFLIGHT CONTROL: redact the unauthorized mailbox
    // secret source: %plaintext remains available only to the authorized party
    // safe effect: the observer endpoint receives the same public zero sentinel
    // reason: the stored value has no data dependence on %plaintext
    // preflight expectation: preserve the constant observer transfer for exact binding
    llvm.call @sps_transfer_party_observer(%zero) {
      sps.contract_ref = "observer-transfer",
      sps.fixture_refs = ["transfer:observer-endpoint"],
      sps.transfer_destination = "observer-mailbox-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.return
  }
}
