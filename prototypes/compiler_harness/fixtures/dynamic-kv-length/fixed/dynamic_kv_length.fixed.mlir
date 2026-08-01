// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic output-memory flow; exact product observes equal count pairs
// scope limit: actual fixed allocation and fixed work are not encoded here
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @dynamic_kv_length_fixed
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[PRIVATE:[a-zA-Z0-9_]+]]: i32, %[[ALLOC:[a-zA-Z0-9_]+]]: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}, %[[ITER:[a-zA-Z0-9_]+]]: !llvm.ptr {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"}
// CHECK-NOT: llvm.store {{.*}}, %[[ALLOC]]
// CHECK-NOT: llvm.store {{.*}}, %[[ITER]]
// CHECK: %[[MAX:[0-9]+]] = llvm.mlir.constant(64 : i32) : i32
// CHECK-NOT: llvm.store {{.*}}, %[[ALLOC]]
// CHECK-NOT: llvm.store {{.*}}, %[[ITER]]
// CHECK: llvm.store %[[MAX]], %[[ALLOC]] {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}
// CHECK-NOT: llvm.store {{.*}}, %[[ALLOC]]
// CHECK-NOT: llvm.store {{.*}}, %[[ITER]]
// CHECK: llvm.store %[[MAX]], %[[ITER]] {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"}
// CHECK-NOT: llvm.store {{.*}}, %[[ALLOC]]
// CHECK-NOT: llvm.store {{.*}}, %[[ITER]]
// CHECK: llvm.return %[[PRIVATE]] : i32
module {
  llvm.func @dynamic_kv_length_fixed(
      %secret_length: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %private_result: i32,
      %public_allocation_count: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"},
      %public_iteration_count: !llvm.ptr {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"}) -> i32 {
    %public_maximum = llvm.mlir.constant(64 : i32) : i32
    // PREFLIGHT CONTROL: write a public fixed allocation-count field
    // secret source: %secret_length is intentionally absent from this store
    // removed observable: every run stores allocation-count value 64
    // reason: %public_maximum is independent of the private sequence length
    // preflight expectation: preflight diagnostic public-output flow is independent of the secret
    llvm.store %public_maximum, %public_allocation_count {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    // PREFLIGHT CONTROL: write a public fixed work-count field
    // secret source: %secret_length is intentionally absent from this store
    // removed observable: every run stores work-count value 64
    // reason: %public_maximum is independent of the private sequence length
    // preflight expectation: preflight diagnostic public-output flow is independent of the secret
    llvm.store %public_maximum, %public_iteration_count {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return %private_result : i32
  }
}
