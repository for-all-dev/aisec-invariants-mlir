// case: kyberslash1/poly_tomsg
// classification: compiler-imported decisive operation
// source revision: pq-crystals/kyber before dda29cc
// compiler: clang 17.0.6 -O0 -Xclang -disable-O0-optnone -target aarch64
// target: AArch64
// SECRET: %coefficient is secret-derived.
// CONFIDENTIALITY BREAK: secret-derived division has variable timing.
module {
  llvm.func @poly_tomsg_bad(%coefficient: i32) -> i32 {
    %two = llvm.mlir.constant(2 : i32) : i32
    %round = llvm.mlir.constant(1664 : i32) : i32
    %q = llvm.mlir.constant(3329 : i32) : i32
    %shifted = llvm.shl %coefficient, %two : i32
    %numerator = llvm.add %shifted, %round : i32
    // CONFIDENTIALITY BREAK: llvm.udiv observes a secret-derived operand.
    %quotient = llvm.udiv %numerator, %q : i32
    llvm.return %quotient : i32
  }
}
