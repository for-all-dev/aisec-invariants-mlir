// Dividing by a secret: on x86 `div` latency depends on its operands, which is what
// layer A's binsec policy assumes about binaries. Obligation 4.
func.func @secret_divisor(%secret: i32 {fcvdct.secret}, %public: i32) -> i32 {
  %quotient = arith.divui %public, %secret : i32
  func.return %quotient : i32
}
