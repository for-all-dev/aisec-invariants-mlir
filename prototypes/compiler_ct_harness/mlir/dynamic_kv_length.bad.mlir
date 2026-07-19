// case: secret-dependent dynamic tensor and KV-cache length
// classification: seeded-semantic-harness
// c source: ../c/dynamic_kv_length_bad.c
// upstream GitHub source: https://github.com/vllm-project/vllm/issues/16016
// upstream revision: none -- this is not a claimed vLLM defect
// secret: %secret_length
// public: private result and public allocation/work observation addresses
// expected verdict: reject when allocation-size and operation-count effects are enabled
// exact incident boundary: planned L1 dynamic-shape effects; L2 supplies a length-pair witness
module {
  llvm.func @dynamic_kv_length_bad(
      %secret_length: i32,
      %private_result: i32,
      %public_allocation_count: !llvm.ptr,
      %public_iteration_count: !llvm.ptr) -> i32 {
    // CONFIDENTIALITY ERROR: secret-dependent allocation size
    // secret source: %secret_length is a private sequence length
    // observable effect: the allocator or memory observer sees the requested capacity
    // reason: two secret lengths produce different public allocation counts
    // detection boundary: L1 once allocation-size effects exist; L2 can return two lengths
    llvm.store %secret_length, %public_allocation_count : i32, !llvm.ptr
    // CONFIDENTIALITY ERROR: secret-dependent operation count
    // secret source: %secret_length is a private sequence length
    // observable effect: the scheduler or timing observer sees the number of iterations
    // reason: two secret lengths produce different public work counts
    // detection boundary: L1 once operation-count effects exist; L2 can return two lengths
    llvm.store %secret_length, %public_iteration_count : i32, !llvm.ptr
    llvm.return %private_result : i32
  }
}
