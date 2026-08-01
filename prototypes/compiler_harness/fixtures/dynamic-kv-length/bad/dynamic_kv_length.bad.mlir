// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic direct output-memory flow; exact product can witness unequal count pairs
// scope limit: no allocation, dynamic shape, loop, or scheduler event is encoded here
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @dynamic_kv_length_bad
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[PRIVATE:[a-zA-Z0-9_]+]]: i32, %[[ALLOC:[a-zA-Z0-9_]+]]: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}, %[[ITER:[a-zA-Z0-9_]+]]: !llvm.ptr {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"}
// CHECK: llvm.store %[[SECRET]], %[[ALLOC]] {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}
// CHECK: llvm.store %[[SECRET]], %[[ITER]] {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"}
module {
  llvm.func @dynamic_kv_length_bad(
      %secret_length: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %private_result: i32,
      %public_allocation_count: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"},
      %public_iteration_count: !llvm.ptr {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"}) -> i32 {
    // PREFLIGHT FINDING: secret-dependent public allocation-count field
    // secret source: %secret_length is a private sequence length
    // observable effect: the public output field contains %secret_length
    // reason: two secret lengths produce different stored allocation-count values
    // preflight expectation: unary scanner flags the candidate-secret allocation-count store
    llvm.store %secret_length, %public_allocation_count {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    // PREFLIGHT FINDING: secret-dependent public work-count field
    // secret source: %secret_length is a private sequence length
    // observable effect: the public output field contains %secret_length
    // reason: two secret lengths produce different stored work-count values
    // preflight expectation: unary scanner flags the candidate-secret work-count store
    llvm.store %secret_length, %public_iteration_count {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return %private_result : i32
  }
}
