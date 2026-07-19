// case: clangover/poly_frommsg
// classification: modeled-from-verified-assembly
// c source: ../c/clangover_poly_frommsg_vulnerable.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L141-L159
// upstream revision: b628ba78711bc28327dc7d2d5c074a00f061884e
// secret: %bit, one bit derived from the message byte
// public: coefficient constant 1665
// expected verdict: reject
// exact incident boundary: L1 target check catches this; L2 can produce bit=0/1 witness; L3 explains compiler regression
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
    llvm.cond_br %bit, ^taken, ^not_taken
  ^taken:
    llvm.return %constant : i16
  ^not_taken:
    llvm.return %zero : i16
  }
}
