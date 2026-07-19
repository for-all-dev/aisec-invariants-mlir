// case: wolfssl/CVE-2026-3579
// classification: compiler-generated-minimized
// c source: ../c/wolfssl_3579_mul_vulnerable.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
// upstream revision: b6fbfad945d4b98fce619b6e5b6561b3eca1205b
// secret: %secret_a and %secret_b
// public: target profile RV32I without the M extension
// expected verdict: target obligation
// exact incident boundary: L1 can flag known helper sinks; exact helper timing is L4 evidence
module {
  llvm.func @wolfssl_3579_mul_source(%secret_a: i64, %secret_b: i64) -> i64 {
    %product = llvm.mul %secret_a, %secret_b : i64
    llvm.return %product : i64
  }
}
