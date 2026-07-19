// case: kyberslash2/compress
// classification: compiler-imported fixed reduction
// source: KyberSlash post-fix compression arithmetic
// compiler: clang 17.0.6 -O0 -Xclang -disable-O0-optnone -target aarch64
// target: AArch64
// SECRET: %coefficient is secret-derived.
// PATCHED: multiply/add/shift replacement contains no division.
module {
  llvm.func @compress_fixed(%coefficient: i32) -> i32 {
    %four = llvm.mlir.constant(4 : i32) : i32
    %round = llvm.mlir.constant(1665 : i32) : i32
    %reciprocal = llvm.mlir.constant(80635 : i32) : i32
    %shift = llvm.mlir.constant(28 : i32) : i32
    %shifted = llvm.shl %coefficient, %four : i32
    %numerator = llvm.add %shifted, %round : i32
    %scaled = llvm.mul %numerator, %reciprocal : i32
    %quotient = llvm.lshr %scaled, %shift : i32
    llvm.return %quotient : i32
  }
}
