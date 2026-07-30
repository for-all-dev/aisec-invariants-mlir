// A masked secret is combined with public data and never steers anything: the
// baseline that must come back secure on every obligation.
func.func @ct_mask(%secret: i32 {fcvdct.secret}, %public: i32) -> i32 {
  %c7 = arith.constant 7 : i32
  %masked = arith.andi %secret, %c7 : i32
  %sum = arith.addi %masked, %public : i32
  func.return %sum : i32
}
