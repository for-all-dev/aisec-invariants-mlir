// case: kyberslash1/poly_tomsg
// classification: compiler-generated-minimized
// c source: ../c/kyberslash1_poly_tomsg_fixed.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/commit/dda29cc63af721981ee2c831cf00822e69be3220
// upstream revision: dda29cc63af721981ee2c831cf00822e69be3220
// secret: %coefficient
// public: KYBER_Q-derived reciprocal and shift constants
// expected verdict: pass
// exact incident boundary: L1 confirms no division remains
module {
  llvm.func @kyberslash1_poly_tomsg_fixed(%coefficient: i32) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %round = llvm.mlir.constant(1665 : i32) : i32
    %reciprocal = llvm.mlir.constant(80635 : i32) : i32
    %shift = llvm.mlir.constant(28 : i32) : i32
    %shifted = llvm.shl %coefficient, %one : i32
    %numerator = llvm.add %shifted, %round : i32
    // CONFIDENTIALITY REPAIR: reciprocal multiply replaces division
    // secret source: %numerator is derived from secret %coefficient
    // safe effect: no division instruction or helper is selected
    // reason: multiply/add/shift sequence preserves the documented bit result on the Kyber coefficient domain
    // detection boundary: L1 confirms forbidden division is absent
    %scaled = llvm.mul %numerator, %reciprocal : i32
    %quotient = llvm.lshr %scaled, %shift : i32
    %bit = llvm.and %quotient, %one : i32
    llvm.return %bit : i32
  }
}
