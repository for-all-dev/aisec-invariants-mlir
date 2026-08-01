// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic reduced sequential model; no real GPU,
// cross-process isolation, or runtime-concurrency claim is made
//
// CHECK-LABEL: llvm.func @leftoverlocals_scratch_fixed
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32, %[[NEXT:[a-zA-Z0-9_]+]]: i32, %[[SCRATCH:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[OUTPUT:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK-NOT: llvm.store {{.*}}, %[[SCRATCH]]
// CHECK-NOT: llvm.store {{.*}}, %[[OUTPUT]]
// CHECK: llvm.store %[[NEXT]], %[[SCRATCH]]
// CHECK-NOT: llvm.store {{.*}}, %[[SCRATCH]]
// CHECK-NOT: llvm.store {{.*}}, %[[OUTPUT]]
// CHECK: %[[INITIALIZED:[0-9]+]] = llvm.load %[[SCRATCH]]
// CHECK-NOT: llvm.store {{.*}}, %[[SCRATCH]]
// CHECK-NOT: llvm.store {{.*}}, %[[OUTPUT]]
// CHECK: llvm.store %[[INITIALIZED]], %[[OUTPUT]]
// CHECK-NOT: llvm.store {{.*}}, %[[SCRATCH]]
// CHECK-NOT: llvm.store {{.*}}, %[[OUTPUT]]
// CHECK: llvm.return %[[NEXT]] : i32
module {
  llvm.func @leftoverlocals_scratch_fixed(
      %prior_tenant_secret: i32,
      %next_tenant_public_value: i32,
      %shared_scratch: !llvm.ptr,
      %next_tenant_output: !llvm.ptr) -> i32 {
    llvm.store %next_tenant_public_value, %shared_scratch : i32, !llvm.ptr
    %initialized = llvm.load %shared_scratch : !llvm.ptr -> i32
    // PREFLIGHT CONTROL: publish only scratch initialized by the current domain
    // secret source: %prior_tenant_secret is absent from %initialized
    // removed observable: next-tenant output is independent of prior-domain data
    // reason: the domain transition overwrites scratch before any current-domain read
    // preflight expectation: direct preflight diagnostic flow check passes for this sequential model
    llvm.store %initialized, %next_tenant_output : i32, !llvm.ptr
    llvm.return %next_tenant_public_value : i32
  }
}
