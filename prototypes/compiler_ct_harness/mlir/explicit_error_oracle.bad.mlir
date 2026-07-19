// case: explicit PKCS#1 padding error oracle
// classification: seeded-semantic-harness
// c source: ../c/explicit_error_oracle_bad.c
// upstream GitHub source: https://github.com/openssl/openssl/blob/1ca61aa56090356bbdbb16cf48916fbd9886c78d/crypto/rsa/rsa_pk1.c#L255-L271
// upstream revision: 1ca61aa56090356bbdbb16cf48916fbd9886c78d
// secret: %padding_is_valid
// public: %authorized_plaintext_length and public status
// expected verdict: reject
// exact incident boundary: L1 for explicit status; L2 for leakage beyond an allowed validity release
module {
  llvm.func @explicit_error_oracle_bad(
      %padding_is_valid: i32,
      %authorized_plaintext_length: i32,
      %public_status: !llvm.ptr) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %valid_bit = llvm.and %padding_is_valid, %one : i32
    %status = llvm.xor %valid_bit, %one : i32
    // CONFIDENTIALITY ERROR: secret-dependent public error status
    // secret source: %status is derived from secret %padding_is_valid
    // observable effect: a caller distinguishes success 0 from failure 1
    // reason: the public status is different for two secret padding-validity inputs
    // detection boundary: direct L1 error-event flow; L2 checks an allowed-release budget
    llvm.store %status, %public_status : i32, !llvm.ptr
    llvm.return %authorized_plaintext_length : i32
  }
}
