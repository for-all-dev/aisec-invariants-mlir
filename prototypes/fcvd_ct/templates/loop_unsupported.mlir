// Coverage control: loops are not modelled, and the answer must say so rather than
// quietly report the fragment it did understand. Expected: UNKNOWN.
builtin.module {
  func.func @source(%n: index, %x: i32) {
    %lb = arith.constant 0 : index
    %step = arith.constant 1 : index
    scf.for %i = %lb to %n step %step {
      %a, %la = "fcvd.hole"(%x) {sym_name = "A", leaks = 1 : i64} : (i32) -> (i32, i32)
      scf.yield
    }
    func.return
  }

  func.func @target(%n: index, %x: i32) {
    %lb = arith.constant 0 : index
    %step = arith.constant 1 : index
    scf.for %i = %lb to %n step %step {
      %a, %la = "fcvd.hole"(%x) {sym_name = "A", leaks = 1 : i64} : (i32) -> (i32, i32)
      scf.yield
    }
    func.return
  }
}
