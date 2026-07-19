// case: wolfssl/CVE-2026-3579
// classification: modeled-fixed-target
// c source: ../c/wolfssl_3579_mul_fixed.c
// upstream GitHub source: https://github.com/wolfSSL/wolfssl/tree/8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5/wolfcrypt/src
// upstream revision: 8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5
// secret: %secret_a and %secret_b
// public: fixed loop count 64 and target profile RV32I without the M extension
// expected verdict: pass with fixed-iteration helper in verified region
// exact incident boundary: L1 accepts the loop shape subject to target operation profile; exact target profile remains L4
module {
  llvm.func @wolfssl_3579_mul_fixed_model(%secret_a: i64, %secret_b: i64) -> i64 {
    %zero64 = llvm.mlir.constant(0 : i64) : i64
    %one64 = llvm.mlir.constant(1 : i64) : i64
    %zero32 = llvm.mlir.constant(0 : i32) : i32
    %one32 = llvm.mlir.constant(1 : i32) : i32
    %sixty_four = llvm.mlir.constant(64 : i32) : i32
    llvm.br ^loop(%zero32, %zero64, %secret_a, %secret_b : i32, i64, i64, i64)
  ^loop(%i: i32, %acc: i64, %addend: i64, %mult: i64):
    %done = llvm.icmp "eq" %i, %sixty_four : i32
    llvm.cond_br %done, ^exit(%acc : i64), ^body
  ^body:
    %low_bit = llvm.and %mult, %one64 : i64
    // CONFIDENTIALITY REPAIR: fixed-iteration mask/add multiplication
    // secret source: %low_bit is a secret bit of %secret_b
    // safe effect: it affects only a mask operand, not loop count, branch direction, address, or helper selection
    // reason: all 64 iterations execute for every input and no __muldi3 call is emitted
    // detection boundary: L1 accepts this shape with a constant-time RV32I operation profile
    %mask = llvm.sub %zero64, %low_bit : i64
    %masked_addend = llvm.and %addend, %mask : i64
    %acc_next = llvm.add %acc, %masked_addend : i64
    %addend_next = llvm.shl %addend, %one64 : i64
    %mult_next = llvm.lshr %mult, %one64 : i64
    %i_next = llvm.add %i, %one32 : i32
    llvm.br ^loop(%i_next, %acc_next, %addend_next, %mult_next : i32, i64, i64, i64)
  ^exit(%result: i64):
    llvm.return %result : i64
  }
}
