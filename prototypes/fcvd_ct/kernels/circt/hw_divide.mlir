// The hardware side of the arcilator finding: a divider fed with a secret. In
// synthesised logic this is a fixed-delay circuit, so under the model of
// `../../templates/circt/comb_to_arith_div.mlir` nothing is observable.
//
// Expected: SECURE.
func.func @hw_divide(%public: i32, %secret: i32 {fcvdct.secret}) -> i32 {
  %q = comb.divu %public, %secret : i32
  func.return %q : i32
}
