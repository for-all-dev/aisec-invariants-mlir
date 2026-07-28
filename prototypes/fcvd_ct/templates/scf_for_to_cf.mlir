// The loop half of `-convert-scf-to-cf`, as a structural specification: an
// `scf.for` becomes the four-block skeleton -- entry branch, header with the
// comparison and the conditional branch, body ending in a branch back, exit.
// The body is a hole, so the statement is about the skeleton, not about a program.
//
// Both sides are unrolled by the same bound, so this says: for runs of up to that
// many iterations, the skeleton observes exactly what the loop observed -- the
// trip-count comparisons and the body's own leakage, nothing more.
//
// Expected: CT-PRESERVING (bounded).
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
    cf.br ^header(%lb : index)
  ^header(%i: index):
    %keep_going = arith.cmpi slt, %i, %n : index
    cf.cond_br %keep_going, ^body, ^exit
  ^body:
    %a, %la = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 1 : i64} : (i32) -> (i32, i32)
    %next = arith.addi %i, %step : index
    cf.br ^header(%next : index)
  ^exit:
    func.return
  }
}
