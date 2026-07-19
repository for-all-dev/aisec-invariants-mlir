// case: wolfssl/CVE-2026-3580
// classification: modeled-from-verified-assembly
// c source: ../c/wolfssl_3580_mask_vulnerable.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
// upstream revision: b6fbfad945d4b98fce619b6e5b6561b3eca1205b
// secret: %table_index
// public: %scan_index, %table_value, and fixed scan bound
// expected verdict: reject
// exact incident boundary: L1/L2 target model; L3 backend evidence; literal GCC MLIR is not claimed
module {
  // Reported RV32I shape:
  //   xor a?, scan_index, table_index
  //   bnez a?, .Lskip
  llvm.func @wolfssl_3580_rv32_bad_model(%table_index: i32, %scan_index: i32, %table_value: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %eq = llvm.icmp "eq" %scan_index, %table_index : i32
    // CONFIDENTIALITY ERROR: secret-dependent branch
    // secret source: %eq depends on secret %table_index
    // observable effect: RV32I bnez/bne direction and timing expose equality with the public scan index
    // reason: two secret indices select different successors for the same public scan iteration
    // detection boundary: L1 if this target model is imported; L2 reports indices such as 0 and 1; L3 stores backend evidence
    llvm.cond_br %eq, ^load, ^skip
  ^load:
    llvm.return %table_value : i32
  ^skip:
    llvm.return %zero : i32
  }
}
