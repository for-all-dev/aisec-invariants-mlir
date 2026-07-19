// case: explicit PKCS#1 padding error oracle
// classification: seeded-semantic-harness
// c source: ../c/explicit_error_oracle_fixed.c
// upstream GitHub source: https://github.com/openssl/openssl/blob/7fc67e0a33102aa47bbaa56533eeecb98c0450f7/crypto/rsa/rsa_pk1.c#L321-L418
// upstream revision: 7fc67e0a33102aa47bbaa56533eeecb98c0450f7
// secret: %padding_is_valid
// public: %authorized_plaintext_length and uniform public status
// expected verdict: pass for the status-channel reduction
// exact incident boundary: L1 here; real synthetic-plaintext indistinguishability is an L4 mechanism obligation
module {
  llvm.func @explicit_error_oracle_fixed(
      %padding_is_valid: i32,
      %authorized_plaintext_length: i32,
      %public_status: !llvm.ptr) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    // CONFIDENTIALITY REPAIR: publish a uniform status
    // secret source: %padding_is_valid is deliberately absent from the status
    // safe effect: a caller observes success 0 for both validity inputs
    // reason: %zero has no data dependence on secret padding validity
    // detection boundary: direct L1 error-event check passes for this reduction
    llvm.store %zero, %public_status : i32, !llvm.ptr
    llvm.return %authorized_plaintext_length : i32
  }
}
