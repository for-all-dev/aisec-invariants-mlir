// RUN: %checkpoint-runner run --snapshot fixtures/leftoverlocals-scratch/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/leftoverlocals-scratch/bad/leftoverlocals_scratch.bad.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic reduced sequential model; no real GPU,
// cross-process isolation, or runtime-concurrency claim is made
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @leftoverlocals_scratch_bad(
      %prior_tenant_secret: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %next_tenant_public_value: i32,
      %shared_scratch: !llvm.ptr,
      %next_tenant_output: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) -> i32 {
    llvm.store %prior_tenant_secret, %shared_scratch : i32, !llvm.ptr
    %residual = llvm.load %shared_scratch : !llvm.ptr -> i32
    // PREFLIGHT FINDING: prior-domain scratch reaches the next domain
    // secret source: %residual was written from %prior_tenant_secret
    // observable effect: the next tenant reads the prior tenant's scratch value
    // reason: no initialization or domain-transition clear occurs before publication
    // preflight expectation: unary scanner flags prior-domain data in the reduced public output
    llvm.store %residual, %next_tenant_output {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return %next_tenant_public_value : i32
  }
}
