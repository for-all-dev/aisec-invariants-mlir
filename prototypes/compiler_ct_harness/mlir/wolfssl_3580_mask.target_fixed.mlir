// case: wolfssl/CVE-2026-3580
// classification: compiler-imported fixed reduction
// source: c/wolfssl_3580_mask_fixed.c
// compiler: clang 17.0.6 -O3 -march=rv32i -mabi=ilp32
// target: RV32I
// SECRET: %table_index.
// PATCHED: equality is converted to a full-word mask and the fixed scan has no secret branch.
module {
  llvm.func @table_mask_rv32_fixed(%table_index: i32, %entry: i32) -> i32 {
    %mask = llvm.call @ct_eq_mask(%entry, %table_index) : (i32, i32) -> i32
    %selected = llvm.and %mask, %entry : i32
    llvm.return %selected : i32
  }
  // The helper is the fixed-width XOR/nonzero construction in the C source.
  llvm.func @ct_eq_mask(%a: i32, %b: i32) -> i32
}
