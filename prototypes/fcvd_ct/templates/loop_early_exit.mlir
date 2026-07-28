// The same loop lowering, plus an "optimisation": the target leaves the loop as soon
// as the body produces a non-zero value. Everybody writes this loop -- search, find,
// memcmp -- and it is the textbook way to turn a constant-time scan into a leak,
// because the number of iterations now depends on the data.
//
// Expected: CT-BREAKING. The source observes only the trip-count comparisons against
// `%n`; the target additionally observes whether the body's value was zero, which the
// source never revealed.
builtin.module {
  func.func @source(%n: index, %x: i32) {
    %lb = arith.constant 0 : index
    %step = arith.constant 1 : index
    scf.for %i = %lb to %n step %step {
      %a, %la = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 1 : i64} : (i32) -> (i32, i32)
      scf.yield
    }
    func.return
  }

  func.func @target(%n: index, %x: i32) {
    %lb = arith.constant 0 : index
    %step = arith.constant 1 : index
    %zero = arith.constant 0 : i32
    cf.br ^header(%lb : index)
  ^header(%i: index):
    %keep_going = arith.cmpi slt, %i, %n : index
    cf.cond_br %keep_going, ^body, ^exit
  ^body:
    %a, %la = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 1 : i64} : (i32) -> (i32, i32)
    %found = arith.cmpi ne, %a, %zero : i32
    cf.cond_br %found, ^exit, ^latch
  ^latch:
    %next = arith.addi %i, %step : index
    cf.br ^header(%next : index)
  ^exit:
    func.return
  }
}
