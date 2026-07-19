// case: wolfssl/CVE-2026-3580
// classification: modeled-fixed-target
// c source: ../c/wolfssl_3580_mask_fixed.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/tree/8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5/wolfcrypt/src
// upstream revision: 8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5
// secret: %table_index
// public: %scan_index, %table_value, and fixed scan bound
// expected verdict: pass
// exact incident boundary: L1 accepts fixed mask selection; L3 can still compare backend output
module {
  llvm.func @wolfssl_3580_select_fixed(%table_index: i32, %scan_index: i32, %table_value: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i32) : i32
    %thirty_one = llvm.mlir.constant(31 : i32) : i32
    %x = llvm.xor %scan_index, %table_index : i32
    %neg_x = llvm.sub %zero, %x : i32
    %nonzero_bits = llvm.or %x, %neg_x : i32
    %top = llvm.lshr %nonzero_bits, %thirty_one : i32
    %is_zero = llvm.xor %top, %one : i32
    // CONFIDENTIALITY REPAIR: branchless equality mask
    // secret source: %table_index contributes only to mask dataflow
    // safe effect: every scan iteration performs the same control flow and table access pattern
    // reason: equality is converted to a full-word mask instead of selecting a successor
    // detection boundary: L1 accepts this target model when the target profile gives these ops constant timing
    %mask = llvm.sub %zero, %is_zero : i32
    %selected = llvm.and %table_value, %mask : i32
    llvm.return %selected : i32
  }
}
