// A branch on a secret: obligation 1 (control flow) must fail, and nothing else.
func.func @secret_branch(%secret: i32 {fcvdct.secret}, %public: i32) -> i32 {
  %zero = arith.constant 0 : i32
  %positive = arith.cmpi sgt, %secret, %zero : i32
  %result = scf.if %positive -> (i32) {
    %doubled = arith.addi %public, %public : i32
    scf.yield %doubled : i32
  } else {
    scf.yield %public : i32
  }
  func.return %result : i32
}
