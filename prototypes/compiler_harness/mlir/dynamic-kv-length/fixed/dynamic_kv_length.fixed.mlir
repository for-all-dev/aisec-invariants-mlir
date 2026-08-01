// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic output-memory flow; exact product observes equal count pairs
// scope limit: actual fixed allocation and fixed work are not encoded here
//
// CHECK-LABEL: llvm.func @dynamic_kv_length_fixed
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32, %[[PRIVATE:[a-zA-Z0-9_]+]]: i32, %[[ALLOC:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[ITER:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK-NOT: llvm.store {{.*}}, %[[ALLOC]]
// CHECK-NOT: llvm.store {{.*}}, %[[ITER]]
// CHECK: %[[MAX:[0-9]+]] = llvm.mlir.constant(64 : i32) : i32
// CHECK-NOT: llvm.store {{.*}}, %[[ALLOC]]
// CHECK-NOT: llvm.store {{.*}}, %[[ITER]]
// CHECK: llvm.store %[[MAX]], %[[ALLOC]]
// CHECK-NOT: llvm.store {{.*}}, %[[ALLOC]]
// CHECK-NOT: llvm.store {{.*}}, %[[ITER]]
// CHECK: llvm.store %[[MAX]], %[[ITER]]
// CHECK-NOT: llvm.store {{.*}}, %[[ALLOC]]
// CHECK-NOT: llvm.store {{.*}}, %[[ITER]]
// CHECK: llvm.return %[[PRIVATE]] : i32
module {
  llvm.func @dynamic_kv_length_fixed(
      %secret_length: i32,
      %private_result: i32,
      %public_allocation_count: !llvm.ptr,
      %public_iteration_count: !llvm.ptr) -> i32 {
    %public_maximum = llvm.mlir.constant(64 : i32) : i32
    // PREFLIGHT CONTROL: write a public fixed allocation-count field
    // secret source: %secret_length is intentionally absent from this store
    // removed observable: every run stores allocation-count value 64
    // reason: %public_maximum is independent of the private sequence length
    // preflight expectation: preflight diagnostic public-output flow is independent of the secret
    llvm.store %public_maximum, %public_allocation_count : i32, !llvm.ptr
    // PREFLIGHT CONTROL: write a public fixed work-count field
    // secret source: %secret_length is intentionally absent from this store
    // removed observable: every run stores work-count value 64
    // reason: %public_maximum is independent of the private sequence length
    // preflight expectation: preflight diagnostic public-output flow is independent of the secret
    llvm.store %public_maximum, %public_iteration_count : i32, !llvm.ptr
    llvm.return %private_result : i32
  }
}
