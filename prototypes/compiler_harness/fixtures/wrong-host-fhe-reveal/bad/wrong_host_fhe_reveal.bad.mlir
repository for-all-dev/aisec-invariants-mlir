// RUN: %checkpoint-runner run --snapshot fixtures/wrong-host-fhe-reveal/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wrong-host-fhe-reveal/bad/wrong_host_fhe_reveal.bad.mlir --records %t.checkpoints

//
// scope note: direct preflight diagnostic host and release-policy violation
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @sps_transfer_fhe_authorized_client(i32)
  llvm.func @sps_transfer_fhe_server(i32)

  llvm.func @wrong_host_fhe_reveal_bad(
      %ciphertext_handle: i32,
      %revealed_plaintext: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i32 {
    llvm.call @sps_transfer_fhe_authorized_client(%revealed_plaintext) {
      sps.contract_ref = "authorized-client-transfer",
      sps.transfer_destination = "authorized-client-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    // PREFLIGHT FINDING: reveal placed on an unauthorized host
    // secret source: %revealed_plaintext is the private result of the modeled reveal
    // observable effect: the server receives plaintext bytes in a host-visible transfer
    // reason: the server is authorized for ciphertext but not for revealed plaintext
    // preflight expectation: preserve the explicit server-destination contract call for exact binding
    llvm.call @sps_transfer_fhe_server(%revealed_plaintext) {
      sps.contract_ref = "server-transfer",
      sps.fixture_refs = ["transfer:server-endpoint"],
      sps.transfer_destination = "server-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.return %ciphertext_handle : i32
  }
}
