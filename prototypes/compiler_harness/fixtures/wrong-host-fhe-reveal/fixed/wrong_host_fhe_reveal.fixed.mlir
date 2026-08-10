// RUN: %checkpoint-runner run --snapshot fixtures/wrong-host-fhe-reveal/fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wrong-host-fhe-reveal/fixed/wrong_host_fhe_reveal.fixed.mlir --records %t.checkpoints

//
// scope note: preflight host/release-policy shape only; cryptographic
// correctness remains outside this reduced model
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @sps_transfer_fhe_authorized_client(i32)
  llvm.func @sps_transfer_fhe_server(i32)

  llvm.func @wrong_host_fhe_reveal_fixed(
      %ciphertext_handle: i32,
      %revealed_plaintext: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i32 {
    llvm.call @sps_transfer_fhe_authorized_client(%revealed_plaintext) {
      sps.contract_ref = "authorized-client-transfer",
      sps.transfer_destination = "authorized-client-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    %zero = llvm.mlir.constant(0 : i32) : i32
    // PREFLIGHT CONTROL: keep server storage plaintext-free
    // secret source: %revealed_plaintext remains only at the authorized client
    // removed observable: the server receives the same public zero sentinel
    // reason: %zero has no dependence on the reveal result
    // preflight expectation: preserve the explicit constant server transfer for exact binding
    llvm.call @sps_transfer_fhe_server(%zero) {
      sps.contract_ref = "server-transfer",
      sps.fixture_refs = ["transfer:server-endpoint"],
      sps.transfer_destination = "server-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.return %ciphertext_handle : i32
  }
}
