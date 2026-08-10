// RUN: %checkpoint-runner run --snapshot fixtures/leftoverlocals-scratch/fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/leftoverlocals-scratch/fixed/leftoverlocals_scratch.fixed.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic reduced sequential model; no real GPU,
// cross-process isolation, or runtime-concurrency claim is made
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @leftoverlocals_scratch_fixed(
      %prior_tenant_secret: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %next_tenant_public_value: i32,
      %shared_scratch: !llvm.ptr,
      %next_tenant_output: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) -> i32 {
    llvm.store %next_tenant_public_value, %shared_scratch : i32, !llvm.ptr
    %initialized = llvm.load %shared_scratch : !llvm.ptr -> i32
    // PREFLIGHT CONTROL: publish only scratch initialized by the current domain
    // secret source: %prior_tenant_secret is absent from %initialized
    // removed observable: next-tenant output is independent of prior-domain data
    // reason: the domain transition overwrites scratch before any current-domain read
    // preflight expectation: direct preflight diagnostic flow check passes for this sequential model
    llvm.store %initialized, %next_tenant_output {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return %next_tenant_public_value : i32
  }
}
