// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: LeftoverLocals residual scratch model
// classification: reduced-runtime-model
// c source: ../c/leftoverlocals_scratch_bad.c
// upstream GitHub source: https://github.com/trailofbits/LeftoverLocalsRelease
// upstream revision: none -- exact behavior is GPU/driver dependent
// secret: %prior_tenant_secret
// public: next-tenant value, scratch address, output address, and domain policy
// expected outcome: unsafe
// observer/model: reduced-sequential-cross-tenant-output
// reason id: cross-domain-stale-state
// outstanding obligations: none
// evidence boundary: L1 reduced sequential model; real cross-process GPU applicability is L4
//
// CHECK-LABEL: llvm.func @leftoverlocals_scratch_bad
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32, %[[NEXT:[a-zA-Z0-9_]+]]: i32, %[[SCRATCH:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[OUTPUT:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK: llvm.store %[[SECRET]], %[[SCRATCH]]
// CHECK: %[[RESIDUAL:[0-9]+]] = llvm.load %[[SCRATCH]]
// CHECK: llvm.store %[[RESIDUAL]], %[[OUTPUT]]
module {
  llvm.func @leftoverlocals_scratch_bad(
      %prior_tenant_secret: i32,
      %next_tenant_public_value: i32,
      %shared_scratch: !llvm.ptr,
      %next_tenant_output: !llvm.ptr) -> i32 {
    llvm.store %prior_tenant_secret, %shared_scratch : i32, !llvm.ptr
    %residual = llvm.load %shared_scratch : !llvm.ptr -> i32
    // CONFIDENTIALITY ERROR: prior-domain scratch reaches the next domain
    // secret source: %residual was written from %prior_tenant_secret
    // observable effect: the next tenant reads the prior tenant's scratch value
    // reason: no initialization or domain-transition clear occurs before publication
    // detection boundary: direct L1 flow in this model; exact GPU isolation is L4
    // expected-error @+1 {{cross-domain-stale-state}}
    llvm.store %residual, %next_tenant_output : i32, !llvm.ptr
    llvm.return %next_tenant_public_value : i32
  }
}
