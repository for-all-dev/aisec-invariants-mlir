// case: clangover/poly_frommsg
// classification: compiler-generated-minimized
// c source: ../c/clangover_poly_frommsg_vulnerable.c
// upstream GitHub source: https://github.com/pq-crystals/kyber/blob/b628ba78711bc28327dc7d2d5c074a00f061884e/ref/poly.c#L141-L159
// upstream revision: b628ba78711bc28327dc7d2d5c074a00f061884e
// secret: %bit, one bit derived from the message byte
// public: coefficient constant 1665
// expected verdict: pass at source form; reject after bad target lowering
// exact incident boundary: L1 catches the lowered branch; L3 attributes compiler introduction
module {
  llvm.func @clangover_poly_frommsg_source(%bit: i16) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    %mask = llvm.sub %zero, %bit : i16
    %coefficient = llvm.and %mask, %constant : i16
    llvm.return %coefficient : i16
  }
}
