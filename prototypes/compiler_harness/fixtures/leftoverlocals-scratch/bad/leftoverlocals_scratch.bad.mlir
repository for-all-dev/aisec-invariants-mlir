// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic reduced sequential model; no real GPU,
// cross-process isolation, or runtime-concurrency claim is made
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @leftoverlocals_scratch_bad
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[NEXT:[a-zA-Z0-9_]+]]: i32, %[[SCRATCH:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[OUTPUT:[a-zA-Z0-9_]+]]: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}
// CHECK: llvm.store %[[SECRET]], %[[SCRATCH]]
// CHECK: %[[RESIDUAL:[0-9]+]] = llvm.load %[[SCRATCH]]
// CHECK: llvm.store %[[RESIDUAL]], %[[OUTPUT]] {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}
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
