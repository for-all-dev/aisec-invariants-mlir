// case: secret logging and checkpoint export
// classification: seeded-semantic-harness
// c source: ../c/secret_logging_checkpoint_bad.c
// upstream GitHub source: https://github.com/kubernetes-sigs/secrets-store-csi-driver/commit/dcb2c294be3bc8b792e02b9f03e5078664db0581
// upstream revision: parent of dcb2c294be3bc8b792e02b9f03e5078664db0581
// secret: %service_account_token
// public: log and artifact-store contents
// expected verdict: reject
// exact incident boundary: L1 with public-log and public-artifact sink summaries
module {
  llvm.func @secret_logging_checkpoint_bad(
      %service_account_token: i32,
      %private_state: !llvm.ptr,
      %public_log: !llvm.ptr,
      %public_checkpoint: !llvm.ptr) {
    llvm.store %service_account_token, %private_state : i32, !llvm.ptr
    // CONFIDENTIALITY ERROR: secret written to a public log
    // secret source: %service_account_token contains authentication material
    // observable effect: log readers can inspect the value stored at %public_log
    // reason: the public store operand is exactly the secret token
    // detection boundary: direct L1 sink violation with a public-log summary
    llvm.store %service_account_token, %public_log : i32, !llvm.ptr
    // CONFIDENTIALITY ERROR: secret exported in a public checkpoint
    // secret source: %service_account_token contains authentication material
    // observable effect: artifact-store readers can inspect %public_checkpoint
    // reason: serialization copies the secret into a public persistent artifact
    // detection boundary: direct L1 sink violation with a public-artifact summary
    llvm.store %service_account_token, %public_checkpoint : i32, !llvm.ptr
    llvm.return
  }
}
