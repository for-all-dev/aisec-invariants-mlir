// case: LeftoverLocals residual scratch model
// classification: reduced-runtime-model
// c source: ../c/leftoverlocals_scratch_fixed.c
// upstream GitHub source: https://github.com/trailofbits/LeftoverLocalsRelease
// upstream revision: none -- exact behavior is GPU/driver dependent
// secret: %prior_tenant_secret
// public: next-tenant value, scratch address, output address, and domain policy
// expected verdict: pass for the explicit sequential model
// exact incident boundary: L1 model; real cross-process GPU persistence remains L4
module {
  llvm.func @leftoverlocals_scratch_fixed(
      %prior_tenant_secret: i32,
      %next_tenant_public_value: i32,
      %shared_scratch: !llvm.ptr,
      %next_tenant_output: !llvm.ptr) -> i32 {
    llvm.store %next_tenant_public_value, %shared_scratch : i32, !llvm.ptr
    %initialized = llvm.load %shared_scratch : !llvm.ptr -> i32
    // CONFIDENTIALITY REPAIR: publish only scratch initialized by the current domain
    // secret source: %prior_tenant_secret is absent from %initialized
    // removed observable: next-tenant output is independent of prior-domain data
    // reason: the domain transition overwrites scratch before any current-domain read
    // detection boundary: direct L1 flow check passes for this sequential model
    llvm.store %initialized, %next_tenant_output : i32, !llvm.ptr
    llvm.return %next_tenant_public_value : i32
  }
}
