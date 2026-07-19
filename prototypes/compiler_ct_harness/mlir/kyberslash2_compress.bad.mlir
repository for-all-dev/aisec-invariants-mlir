// case: kyberslash2/compress
// classification: compiler-imported decisive operation
// source: KyberSlash pre-fix compression arithmetic
// compiler: clang 17.0.6 -O0 -Xclang -disable-O0-optnone -target aarch64
// target: AArch64
// SECRET: %coefficient is secret-derived.
// CONFIDENTIALITY BREAK: the compression quotient uses secret-dependent division.
module {
  llvm.func @compress_bad(%coefficient: i32) -> i32 {
    %four = llvm.mlir.constant(4 : i32) : i32
    %round = llvm.mlir.constant(1664 : i32) : i32
    %q = llvm.mlir.constant(3329 : i32) : i32
    %shifted = llvm.shl %coefficient, %four : i32
    %numerator = llvm.add %shifted, %round : i32
    // CONFIDENTIALITY BREAK: llvm.udiv is on a secret-derived value.
    %quotient = llvm.udiv %numerator, %q : i32
    llvm.return %quotient : i32
  }
}
