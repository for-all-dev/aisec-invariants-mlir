// case: wolfssl/CVE-2026-3579
// classification: modeled-from-verified-assembly
// c source: ../c/wolfssl_3579_mul_vulnerable.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
// upstream revision: b6fbfad945d4b98fce619b6e5b6561b3eca1205b
// secret: %secret_a and %secret_b
// public: target profile RV32I without the M extension
// expected verdict: reject or unresolved target obligation
// exact incident boundary: L1 with known-helper summary; exact operand-dependent timing is L4
module {
  llvm.func @__muldi3(%a: i64, %b: i64) -> i64

  llvm.func @wolfssl_3579_mul_rv32_bad_model(%secret_a: i64, %secret_b: i64) -> i64 {
    // Verified RV32I shape: call __muldi3 for i64 multiplication without the M extension.
    // CONFIDENTIALITY ERROR: variable-time compiler helper
    // secret source: both operands to @__muldi3 are secret
    // observable effect: helper latency depends on operand values in the affected target profile
    // reason: source-level llvm.mul is legalized outside the verified region to a helper with data-dependent timing
    // detection boundary: L1 can reject known variable-time helper summaries; exact helper proof is L4
    %product = llvm.call @__muldi3(%secret_a, %secret_b) : (i64, i64) -> i64
    llvm.return %product : i64
  }
}
