// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: secret-dependent dynamic tensor and KV-cache length
// classification: seeded-semantic-harness
// c source: ../c/dynamic_kv_length_bad.c
// upstream GitHub source: https://github.com/vllm-project/vllm/issues/16016
// upstream revision: none -- this is not a claimed vLLM defect
// secret: %secret_length and private return payload %private_result
// public: stored count fields; the returned %private_result is outside this public boundary
// expected outcome: unsafe
// observer/model: reduced-public-count-output
// reason id: secret-to-public-sink
// outstanding obligations: none
// evidence boundary: L1 direct output-memory flow; L2 can witness unequal count pairs
// L4 extrapolation: no allocation, dynamic shape, loop, or scheduler event is encoded here
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
    // CONFIDENTIALITY ERROR: secret-dependent public allocation-count field
    // secret source: %secret_length is a private sequence length
    // observable effect: the public output field contains %secret_length
    // reason: two secret lengths produce different stored allocation-count values
    // detection boundary: L1 direct secret-to-public store; L2 can return the value pair
    // expected-error @+1 {{secret-to-public-sink}}
    llvm.store %secret_length, %public_allocation_count : i32, !llvm.ptr
    // CONFIDENTIALITY ERROR: secret-dependent public work-count field
    // secret source: %secret_length is a private sequence length
    // observable effect: the public output field contains %secret_length
    // reason: two secret lengths produce different stored work-count values
    // detection boundary: L1 direct secret-to-public store; L2 can return the value pair
    // expected-error @+1 {{secret-to-public-sink}}
    llvm.store %secret_length, %public_iteration_count : i32, !llvm.ptr
    llvm.return %private_result : i32
  }
}
