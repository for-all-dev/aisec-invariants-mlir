// RUN: %checkpoint-runner run --snapshot fixtures/dynamic-kv-length/fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/dynamic-kv-length/fixed/dynamic_kv_length.fixed.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic output-memory flow; exact product observes equal count pairs
// scope limit: actual fixed allocation and fixed work are not encoded here
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
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
