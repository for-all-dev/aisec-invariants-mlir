// case: secret logging and checkpoint export
// classification: seeded-semantic-harness
// c source: ../c/secret_logging_checkpoint_fixed.c
// upstream GitHub source: https://github.com/kubernetes-sigs/secrets-store-csi-driver/commit/dcb2c294be3bc8b792e02b9f03e5078664db0581
// upstream revision: dcb2c294be3bc8b792e02b9f03e5078664db0581
// secret: %service_account_token
// public: log and artifact-store contents plus the zero redaction sentinel
// expected verdict: pass
// exact incident boundary: L1 with public-log and public-artifact sink summaries
module {
  llvm.func @secret_logging_checkpoint_fixed(
      %service_account_token: i32,
      %private_state: !llvm.ptr,
      %public_log: !llvm.ptr,
      %public_checkpoint: !llvm.ptr) {
    llvm.store %service_account_token, %private_state : i32, !llvm.ptr
    %zero = llvm.mlir.constant(0 : i32) : i32
    // CONFIDENTIALITY REPAIR: redact the public log field
    // secret source: %service_account_token remains only in %private_state
    // safe effect: log readers observe the same public zero sentinel
    // reason: %zero has no data dependence on the token
    // detection boundary: direct L1 public-log sink check passes
    llvm.store %zero, %public_log : i32, !llvm.ptr
    // CONFIDENTIALITY REPAIR: redact the public checkpoint field
    // secret source: %service_account_token remains only in %private_state
    // safe effect: artifact readers observe the same public zero sentinel
    // reason: %zero has no data dependence on the token
    // detection boundary: direct L1 public-artifact sink check passes
    llvm.store %zero, %public_checkpoint : i32, !llvm.ptr
    llvm.return
  }
}
