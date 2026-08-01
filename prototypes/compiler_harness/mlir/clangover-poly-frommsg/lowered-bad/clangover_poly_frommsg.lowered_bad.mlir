// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic target check; exact product bit witness; backend evidence
// artifact status: hand-written target model derived from verified assembly
//
// CHECK-LABEL: llvm.func @clangover_poly_frommsg_x86_bad_model
// CHECK-SAME: %[[BIT:[a-zA-Z0-9_]+]]: i1
// CHECK: llvm.cond_br %[[BIT]], ^bb1, ^bb2
module {
  // Verified x86 excerpt from the reduction:
  //   btl %ecx, %r8d
  //   jae .LBB0_4
  llvm.func @clangover_poly_frommsg_x86_bad_model(%bit: i1) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    // PREFLIGHT FINDING: secret-dependent branch
    // secret source: %bit is derived from the secret message
    // observable effect: branch direction and execution timing
    // reason: inputs differing only in %bit select different successors
    // preflight expectation: unary scanner flags the candidate-secret branch in this target model
    llvm.cond_br %bit, ^taken, ^not_taken
  ^taken:
    llvm.return %constant : i16
  ^not_taken:
    llvm.return %zero : i16
  }
}
