builtin.module {
  func.func private @foo(%pub: i8, %s1: i8, %s2: i8) -> i8 {
    %c3 = arith.constant 3 : i8
    %d  = arith.subi %c3, %c3 : i8
    func.return %d : i8
  }
}
