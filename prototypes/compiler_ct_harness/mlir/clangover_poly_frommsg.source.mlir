// case: clangover/poly_frommsg
// classification: compiler-imported decisive operation (LLVM 17 reproduction)
// source: c/clangover_poly_frommsg_vulnerable.c
// compiler: Homebrew clang 17.0.6 -Os -fno-vectorize -fno-slp-vectorize
// target: x86_64
// SECRET: %bit is one bit of the message byte.
// PUBLIC: 1665 is a public modulus-derived constant.
module {
  llvm.func @poly_frommsg_mask(%bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    %mask = llvm.sub %zero, %bit : i16
    %coefficient = llvm.and %mask, %constant : i16
    llvm.return %coefficient : i16
  }
}
