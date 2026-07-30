// Coverage control: no float semantics exist upstream, so the answer must be
// `unknown` -- never a silent `secure`.
func.func @unsupported_float(%secret: f32 {fcvdct.secret}, %public: f32) -> f32 {
  %sum = arith.addf %secret, %public : f32
  func.return %sum : f32
}
