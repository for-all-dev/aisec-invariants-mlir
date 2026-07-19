// case: kyberslash1/poly_tomsg
// classification: compiler-generated-minimized
// c source: ../c/kyberslash1_poly_tomsg_vulnerable.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L180-L198
// upstream revision: b628ba78711bc28327dc7d2d5c074a00f061884e
// secret: %coefficient
// public: KYBER_Q=3329 and rounding constants
// expected verdict: reject
// exact incident boundary: direct L1 variable-time division check
module {
  llvm.func @kyberslash1_poly_tomsg_bad(%coefficient: i32) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %round = llvm.mlir.constant(1664 : i32) : i32
    %q = llvm.mlir.constant(3329 : i32) : i32
    %shifted = llvm.shl %coefficient, %one : i32
    %numerator = llvm.add %shifted, %round : i32
    // CONFIDENTIALITY ERROR: secret-dependent division
    // secret source: %numerator is derived from secret %coefficient
    // observable effect: division latency can vary with the numerator value
    // reason: inputs differing only in %coefficient execute a variable-time llvm.udiv
    // detection boundary: direct L1 source/LLVM-dialect check
    %quotient = llvm.udiv %numerator, %q : i32
    %bit = llvm.and %quotient, %one : i32
    llvm.return %bit : i32
  }
}
