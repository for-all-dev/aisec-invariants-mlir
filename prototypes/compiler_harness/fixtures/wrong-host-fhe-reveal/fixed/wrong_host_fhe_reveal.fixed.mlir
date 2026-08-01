// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight host/release-policy shape only; cryptographic
// correctness remains outside this reduced model
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @wrong_host_fhe_reveal_fixed
// CHECK-SAME: %[[CIPHERTEXT:[a-zA-Z0-9_]+]]: i32, %[[PLAINTEXT:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[CLIENT:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[SERVER:[a-zA-Z0-9_]+]]: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}
// CHECK-NOT: llvm.store {{.*}}, %[[SERVER]]
// CHECK: llvm.store %[[PLAINTEXT]], %[[CLIENT]]
// CHECK-NOT: llvm.store {{.*}}, %[[SERVER]]
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK-NOT: llvm.store {{.*}}, %[[SERVER]]
// CHECK: llvm.store %[[ZERO]], %[[SERVER]] {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}
// CHECK-NOT: llvm.store {{.*}}, %[[SERVER]]
// CHECK: llvm.return %[[CIPHERTEXT]] : i32
module {
  llvm.func @wrong_host_fhe_reveal_fixed(
      %ciphertext_handle: i32,
      %revealed_plaintext: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %authorized_client_plaintext: !llvm.ptr,
      %unauthorized_server_plaintext: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) -> i32 {
    llvm.store %revealed_plaintext, %authorized_client_plaintext : i32, !llvm.ptr
    %zero = llvm.mlir.constant(0 : i32) : i32
    // PREFLIGHT CONTROL: keep server storage plaintext-free
    // secret source: %revealed_plaintext remains only at the authorized client
    // removed observable: the server observes the same public zero sentinel
    // reason: %zero has no dependence on the reveal result
    // preflight expectation: direct preflight diagnostic host-authority and release-policy check passes
    llvm.store %zero, %unauthorized_server_plaintext {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return %ciphertext_handle : i32
  }
}
