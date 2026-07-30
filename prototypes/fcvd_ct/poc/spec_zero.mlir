builtin.module {
  func.func private @foo(%pub: i8, %s1: i8, %s2: i8) -> i8 {
    %z = arith.constant 0 : i8
    func.return %z : i8
  }
}
