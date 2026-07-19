// case: secret-dependent dynamic tensor and KV-cache length
// classification: seeded-semantic-harness
// c source: ../c/dynamic_kv_length_fixed.c
// upstream GitHub source: https://github.com/vllm-project/vllm/issues/16016
// upstream revision: none -- this is not a claimed vLLM defect
// secret: %secret_length and private return payload %private_result
// public: stored count fields and constant 64; the return is outside this public boundary
// expected verdict: verified for the reduced public-count-output model
// exact incident boundary: L1 output-memory flow; L2 observes equal count pairs
// L4 extrapolation: actual fixed allocation and fixed work are not encoded here
module {
  llvm.func @dynamic_kv_length_fixed(
      %secret_length: i32,
      %private_result: i32,
      %public_allocation_count: !llvm.ptr,
      %public_iteration_count: !llvm.ptr) -> i32 {
    %public_maximum = llvm.mlir.constant(64 : i32) : i32
    // CONFIDENTIALITY REPAIR: write a public fixed allocation-count field
    // secret source: %secret_length is intentionally absent from this store
    // removed observable: every run stores allocation-count value 64
    // reason: %public_maximum is independent of the private sequence length
    // detection boundary: L1 public-output flow is independent of the secret
    llvm.store %public_maximum, %public_allocation_count : i32, !llvm.ptr
    // CONFIDENTIALITY REPAIR: write a public fixed work-count field
    // secret source: %secret_length is intentionally absent from this store
    // removed observable: every run stores work-count value 64
    // reason: %public_maximum is independent of the private sequence length
    // detection boundary: L1 public-output flow is independent of the secret
    llvm.store %public_maximum, %public_iteration_count : i32, !llvm.ptr
    llvm.return %private_result : i32
  }
}
