// case: wolfssl/CVE-2026-3580
// classification: compiler-generated-minimized
// c source: ../c/wolfssl_3580_mask_vulnerable.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
// upstream revision: b6fbfad945d4b98fce619b6e5b6561b3eca1205b
// secret: %table_index
// public: %scan_index, %table_value, and fixed scan bound
// expected verdict: pass at source form; reject if lowered to a target branch
// exact incident boundary: L1/L2 if branch is imported or modeled; L3 backend evidence
module {
  llvm.func @wolfssl_3580_select_source(%table_index: i32, %scan_index: i32, %table_value: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %eq = llvm.icmp "eq" %scan_index, %table_index : i32
    %eq32 = llvm.zext %eq : i1 to i32
    %mask = llvm.sub %zero, %eq32 : i32
    %selected = llvm.and %table_value, %mask : i32
    llvm.return %selected : i32
  }
}
