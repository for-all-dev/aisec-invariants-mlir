// case: wolfssl/CVE-2026-3580
// classification: compiler-imported source reduction
// source: c/wolfssl_3580_mask_vulnerable.c
// compiler: clang 17.0.6 -O3 -march=rv32i -mabi=ilp32 (LLVM IR import)
// SECRET: %table_index selects a table entry.
// PUBLIC: the 16-entry scan bound is fixed.
module {
  llvm.func @table_mask_source(%table_index: i32, %entry: i32) -> i32 {
    %equal = llvm.icmp "eq" %table_index, %entry : i32
    %mask = llvm.sext %equal : i1 to i32
    %selected = llvm.and %mask, %entry : i32
    llvm.return %selected : i32
  }
}
