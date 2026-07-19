// case: clangover/poly_frommsg
// classification: modeled-from-verified-assembly (the imported LLVM IR remains branchless)
// source revision: pq-crystals/kyber b628ba7
// compiler: clang 17.0.6 -Os -fno-vectorize -fno-slp-vectorize
// target: x86_64
// SECRET: %bit is derived from %msg.
// CONFIDENTIALITY BREAK: the backend makes the secret bit a branch condition.
module {
  llvm.func @poly_frommsg_mask(%bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    %mask = llvm.sub %zero, %bit : i16
    %coefficient = llvm.and %mask, %constant : i16
    llvm.return %coefficient : i16
  }

  // Verified x86 excerpt: btl %ecx, %r8d; jae .LBB0_4; movl $1665, %edx
  // CONFIDENTIALITY BREAK: `jae` depends on the selected message bit.
  llvm.func @poly_frommsg_x86_bad_model(%bit: i1) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    llvm.cond_br %bit, ^set, ^clear
  ^set:
    llvm.return %constant : i16
  ^clear:
    llvm.return %zero : i16
  }
}
