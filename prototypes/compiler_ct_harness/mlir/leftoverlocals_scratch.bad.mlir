// case: LeftoverLocals residual scratch model
// classification: reduced-runtime-model
// c source: ../c/leftoverlocals_scratch_bad.c
// upstream GitHub source: https://github.com/trailofbits/LeftoverLocalsRelease
// upstream revision: none -- exact behavior is GPU/driver dependent
// secret: %prior_tenant_secret
// public: next-tenant value, scratch address, output address, and domain policy
// expected verdict: reject for the explicit sequential model
// exact incident boundary: reduced model at L1; real cross-process GPU persistence requires L4
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
    llvm.store %residual, %next_tenant_output : i32, !llvm.ptr
    llvm.return %next_tenant_public_value : i32
  }
}
