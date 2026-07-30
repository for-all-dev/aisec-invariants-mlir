// self-composition, leak = address/index value; index derived from public data only
builtin.module {
  func.func private @foo(%pub: i8, %s1: i8, %s2: i8) -> i8 {
    %c3 = arith.constant 3 : i8
    %a1 = arith.andi %pub, %c3 : i8
    %a2 = arith.andi %pub, %c3 : i8
    %d  = arith.subi %a1, %a2 : i8
    func.return %d : i8
  }
}
