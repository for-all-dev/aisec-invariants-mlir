// case: clangover/poly_frommsg
// classification: compiler-generated-minimized
// c source: ../c/clangover_poly_frommsg_fixed.c
// upstream GitHub source: https://github.com/antoonpurnal/clangover/tree/7f4d5dc162b77c362a34a0d52949f7a3e1b16d81
// upstream revision: 7f4d5dc162b77c362a34a0d52949f7a3e1b16d81
// secret: %bit, one bit derived from the message byte
// public: coefficient constant 1665 and helper arguments
// expected verdict: pass with helper reviewed or inlined into the verified region
// exact incident boundary: L1 checks no secret branch in this fixture; helper obligation is explicit
module {
  llvm.func @clangover_ct_cmov_model(%if_zero: i16, %if_one: i16, %bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %all_ones = llvm.mlir.constant(-1 : i16) : i16
    // CONFIDENTIALITY REPAIR: mask-based conditional move
    // secret source: %bit is used only to construct a full-word mask
    // safe effect: control flow and memory addresses are independent of %bit
    // reason: both values are combined through dataflow rather than successor selection
    // detection boundary: L1 accepts this operation shape subject to target profile
    %mask = llvm.sub %zero, %bit : i16
    %not_mask = llvm.xor %mask, %all_ones : i16
    %left = llvm.and %if_zero, %not_mask : i16
    %right = llvm.and %if_one, %mask : i16
    %selected = llvm.or %left, %right : i16
    llvm.return %selected : i16
  }

  llvm.func @clangover_poly_frommsg_fixed(%bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    %coefficient = llvm.call @clangover_ct_cmov_model(%zero, %constant, %bit) : (i16, i16, i16) -> i16
    llvm.return %coefficient : i16
  }
}
