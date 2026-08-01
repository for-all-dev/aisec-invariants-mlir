// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic direct output-memory flow; exact product can witness unequal count pairs
// scope limit: no allocation, dynamic shape, loop, or scheduler event is encoded here
//
// CHECK-LABEL: llvm.func @dynamic_kv_length_bad
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32, %[[PRIVATE:[a-zA-Z0-9_]+]]: i32, %[[ALLOC:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[ITER:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK: llvm.store %[[SECRET]], %[[ALLOC]]
// CHECK: llvm.store %[[SECRET]], %[[ITER]]
module {
  llvm.func @dynamic_kv_length_bad(
      %secret_length: i32,
      %private_result: i32,
      %public_allocation_count: !llvm.ptr,
      %public_iteration_count: !llvm.ptr) -> i32 {
    // PREFLIGHT FINDING: secret-dependent public allocation-count field
    // secret source: %secret_length is a private sequence length
    // observable effect: the public output field contains %secret_length
    // reason: two secret lengths produce different stored allocation-count values
    // preflight expectation: unary scanner flags the candidate-secret allocation-count store
    llvm.store %secret_length, %public_allocation_count : i32, !llvm.ptr
    // PREFLIGHT FINDING: secret-dependent public work-count field
    // secret source: %secret_length is a private sequence length
    // observable effect: the public output field contains %secret_length
    // reason: two secret lengths produce different stored work-count values
    // preflight expectation: unary scanner flags the candidate-secret work-count store
    llvm.store %secret_length, %public_iteration_count : i32, !llvm.ptr
    llvm.return %private_result : i32
  }
}
