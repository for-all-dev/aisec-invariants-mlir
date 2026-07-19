// case: secret-dependent dynamic tensor and KV-cache length
// classification: seeded-semantic-harness
// c source: ../c/dynamic_kv_length_fixed.c
// upstream GitHub source: https://github.com/vllm-project/vllm/issues/16016
// upstream revision: none -- this is not a claimed vLLM defect
// secret: %secret_length
// public: private result, public maximum 64, and observation addresses
// expected verdict: pass for the modeled allocation and operation-count effects
// exact incident boundary: planned L1/L2 dynamic-shape semantics
module {
  llvm.func @dynamic_kv_length_fixed(
      %secret_length: i32,
      %private_result: i32,
      %public_allocation_count: !llvm.ptr,
      %public_iteration_count: !llvm.ptr) -> i32 {
    %public_maximum = llvm.mlir.constant(64 : i32) : i32
    // CONFIDENTIALITY REPAIR: allocate a public fixed capacity
    // secret source: %secret_length is intentionally absent from this store
    // removed observable: every run reports allocation capacity 64
    // reason: %public_maximum is independent of the private sequence length
    // detection boundary: L1 allocation-size effect passes for this model
    llvm.store %public_maximum, %public_allocation_count : i32, !llvm.ptr
    // CONFIDENTIALITY REPAIR: execute a public fixed work count
    // secret source: %secret_length is intentionally absent from this store
    // removed observable: every run reports 64 externally visible iterations
    // reason: %public_maximum is independent of the private sequence length
    // detection boundary: L1 operation-count effect passes for this model
    llvm.store %public_maximum, %public_iteration_count : i32, !llvm.ptr
    llvm.return %private_result : i32
  }
}
