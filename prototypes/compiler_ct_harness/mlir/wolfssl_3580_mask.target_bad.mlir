// case: wolfssl/CVE-2026-3580
// classification: modeled-from-reported-GCC-assembly
// source: c/wolfssl_3580_mask_vulnerable.c
// compiler: GCC -O3 -march=rv32i -mabi=ilp32 (historical configuration)
// target: RV32I
// SECRET: %table_index is the secret table index.
// CONFIDENTIALITY BREAK: GCC's `bnez`/`bne` makes the secret equality observable.
module {
  // The real clang-imported LLVM dialect remains select-based.  This is the
  // target-level model of the reported GCC assembly, not GCC-generated MLIR.
  llvm.func @table_mask_rv32_bad_model(%table_index: i32) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i32) : i32
    %is_zero = llvm.icmp "eq" %table_index, %zero : i32
    // CONFIDENTIALITY BREAK: bnez a?, .Lskip (condition derived from secret index).
    llvm.cond_br %is_zero, ^load, ^skip
  ^load:
    llvm.return %one : i32
  ^skip:
    llvm.return %zero : i32
  }
}
