// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: clangover/poly_frommsg
// classification: modeled-from-verified-assembly
// c source: ../c/clangover_poly_frommsg_vulnerable.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L141-L159
// upstream revision: b628ba78711bc28327dc7d2d5c074a00f061884e
// secret: %bit, one bit derived from the message byte
// public: coefficient constant 1665
// expected outcome: unsafe
// observer/model: x86-control-flow-timing
// reason id: secret-dependent-branch
// outstanding obligations: none
// evidence boundary: L1 target check; L2 bit witness; L3 compiler-regression evidence
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
    // CONFIDENTIALITY ERROR: secret-dependent branch
    // secret source: %bit is derived from the secret message
    // observable effect: branch direction and execution timing
    // reason: inputs differing only in %bit select different successors
    // detection boundary: L1 here; L2 reports bit=0/1; L3 attributes compiler introduction
    // expected-error @+1 {{secret-dependent-branch}}
    llvm.cond_br %bit, ^taken, ^not_taken
  ^taken:
    llvm.return %constant : i16
  ^not_taken:
    llvm.return %zero : i16
  }
}
