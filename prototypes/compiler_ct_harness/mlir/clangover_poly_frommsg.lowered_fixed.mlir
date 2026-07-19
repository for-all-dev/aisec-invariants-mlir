// case: clangover/poly_frommsg
// classification: compiler-imported fixed reduction
// source: c/clangover_poly_frommsg_fixed.c + c/clangover_ct_cmov.c
// compiler: clang 17.0.6 -Os -fno-vectorize -fno-slp-vectorize, no LTO
// target: x86_64
// SECRET: %bit is data passed to a separately compiled conditional-move helper.
// PATCHED: the caller has no secret-dependent branch; the helper is an explicit review boundary.
module {
  llvm.func @clangover_ct_cmov(%zero: i16, %one: i16, %bit: i16) -> i16

  llvm.func @poly_frommsg_fixed(%bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    %masked = llvm.call @clangover_ct_cmov(%zero, %constant, %bit) : (i16, i16, i16) -> i16
    llvm.return %masked : i16
  }
}
