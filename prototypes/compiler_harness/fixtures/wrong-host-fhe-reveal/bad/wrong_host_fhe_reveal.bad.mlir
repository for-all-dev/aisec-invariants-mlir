// RUN: %checkpoint-runner run --snapshot fixtures/wrong-host-fhe-reveal/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/wrong-host-fhe-reveal/bad/wrong_host_fhe_reveal.bad.mlir --records %t.checkpoints

//
// scope note: direct preflight diagnostic host and release-policy violation
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @wrong_host_fhe_reveal_bad(
      %ciphertext_handle: i32,
      %revealed_plaintext: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %authorized_client_plaintext: !llvm.ptr,
      %unauthorized_server_plaintext: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) -> i32 {
    llvm.store %revealed_plaintext, %authorized_client_plaintext : i32, !llvm.ptr
    // PREFLIGHT FINDING: reveal placed on an unauthorized host
    // secret source: %revealed_plaintext is the private result of the modeled reveal
    // observable effect: the server can read plaintext from its mailbox
    // reason: the server is authorized for ciphertext but not for revealed plaintext
    // preflight expectation: direct preflight diagnostic host-authority and release-policy check
    llvm.store %revealed_plaintext, %unauthorized_server_plaintext {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return %ciphertext_handle : i32
  }
}
