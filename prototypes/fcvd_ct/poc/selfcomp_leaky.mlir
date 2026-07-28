// self-composition, leak = address/index value; index derived from the secret
builtin.module {
  func.func private @foo(%pub: i8, %s1: i8, %s2: i8) -> i8 {
    %a1 = arith.andi %s1, %pub : i8
    %a2 = arith.andi %s2, %pub : i8
    %d  = arith.subi %a1, %a2 : i8
    func.return %d : i8
  }
}
