// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: reduced placement/output-policy shape only; the linked hosted
// incident is not encoded by this fixture
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @wrong_party_plaintext_bad
// CHECK-SAME: %[[PLAINTEXT:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[AUTHORIZED:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[UNAUTHORIZED:[a-zA-Z0-9_]+]]: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}
// CHECK: llvm.store %[[PLAINTEXT]], %[[AUTHORIZED]]
// CHECK: llvm.store %[[PLAINTEXT]], %[[UNAUTHORIZED]] {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}
module {
  llvm.func @wrong_party_plaintext_bad(
      %plaintext: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %authorized_mailbox: !llvm.ptr,
      %unauthorized_mailbox: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) {
    llvm.store %plaintext, %authorized_mailbox : i32, !llvm.ptr
    // PREFLIGHT FINDING: wrong-party plaintext store
    // secret source: %plaintext is owned by the authorized party
    // observable effect: the unauthorized party can read its mailbox contents
    // reason: this store copies the secret verbatim across the audience boundary
    // preflight expectation: direct preflight diagnostic placement and output-policy violation
    llvm.store %plaintext, %unauthorized_mailbox {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
