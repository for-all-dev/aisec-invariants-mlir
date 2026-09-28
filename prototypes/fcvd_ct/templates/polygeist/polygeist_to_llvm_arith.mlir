// Polygeist `--convert-polygeist-to-llvm` (driver.cc:1009, pass assembled in
// lib/polygeist/Passes/ConvertPolygeistToLLVM.cpp:2846-2856). The pass is a bundle;
// this template specifies its INTEGER-ARITHMETIC slice, which arrives through
// upstream's ArithToLLVM patterns (llvm-project @ 26eb4285,
// mlir/lib/Conversion/ArithToLLVM/ArithToLLVM.cpp — AddIOpLowering :37,
// MulIOpLowering :80, SubIOpLowering :104: each arith op maps 1:1 onto its llvm
// twin). The scf→cf slice the same bundle pulls in (:2848,
// populateSCFToControlFlowConversionPatterns) is specified by the general templates
// scf_for_to_cf.mlir / scf_if_to_cf.mlir, registered for this step in the descriptor.
// The memref→llvm slice (getelementptr arithmetic) is NOT specified: llvm memory ops
// have no SMT semantics upstream — recorded as the step's open half in the journal.
//
// Pure arithmetic emits no observation in the leakage model, so the constant-time
// half is vacuous here (0 observations, printed as such) and the equivalence half
// carries the claim. The falsifying twin is polygeist_to_llvm_swapped_sub.mlir.
//
// Swept over the integer width W (issue #63: the rule is width-generic, one i64
// instance was not); i1 included, where add/sub/mul degenerate to xor/xor/and and
// wrap-around is everywhere.
//
// Expected on every instance: CT-PRESERVING (vacuously, 0 -> 0) and EQUIVALENT.
// fcvdct.sweep W = i1, i8, i16, i32, i64
builtin.module {
  func.func @source(%a: ${W}, %b: ${W}) -> i64 {
    %sum = arith.addi %a, %b : ${W}
    %prod = arith.muli %sum, %a : ${W}
    %diff = arith.subi %prod, %b : ${W}
    func.return %diff : ${W}
  }

  func.func @target(%a: ${W}, %b: ${W}) -> i64 {
    %sum = llvm.add %a, %b : ${W}
    %prod = llvm.mul %sum, %a : ${W}
    %diff = llvm.sub %prod, %b : ${W}
    func.return %diff : ${W}
  }
}
