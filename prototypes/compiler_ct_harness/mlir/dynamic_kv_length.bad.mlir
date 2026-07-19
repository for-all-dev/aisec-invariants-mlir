// case: secret-dependent dynamic tensor and KV-cache length
// classification: seeded-semantic-harness
// c source: ../c/dynamic_kv_length_bad.c
// upstream GitHub source: https://github.com/vllm-project/vllm/issues/16016
// upstream revision: none -- this is not a claimed vLLM defect
// secret: %secret_length and private return payload %private_result
// public: stored count fields; the returned %private_result is outside this public boundary
// expected verdict: unsafe for the reduced public-count-output model
// exact incident boundary: L1 direct output-memory flow; L2 can witness unequal count pairs
// L4 extrapolation: no allocation, dynamic shape, loop, or scheduler event is encoded here
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
    llvm.store %secret_length, %public_allocation_count : i32, !llvm.ptr
    // CONFIDENTIALITY ERROR: secret-dependent public work-count field
    // secret source: %secret_length is a private sequence length
    // observable effect: the public output field contains %secret_length
    // reason: two secret lengths produce different stored work-count values
    // detection boundary: L1 direct secret-to-public store; L2 can return the value pair
    llvm.store %secret_length, %public_iteration_count : i32, !llvm.ptr
    llvm.return %private_result : i32
  }
}
