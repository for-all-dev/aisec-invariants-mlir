// A lowering bug: the arms are exchanged, so the target runs the else-code when the
// condition holds. Value-wise a miscompilation; leakage-wise the target makes the
// observations of the arm the source did not take.
//
// Expected: CT-BREAKING. Together with `scf_if_to_cf` -- the same lowering with the
// arms in the right order, which comes back preserving -- this pins down that hole
// identity is what is being checked, not just hole count.
//
// (Measured, not assumed: deleting the congruence axioms does *not* make the corpus
// pass. It makes `scf_if_to_cf` fail instead, because the target's holes become
// unrelated symbols. The axioms are what let a correct lowering be provable at all.)
builtin.module {
  func.func @source(%c: i1, %x: i32) {
    %r = scf.if %c -> (i32) {
      %a, %la = "fcvd.hole"(%x) {sym_name = "A", leaks = 1 : i64} : (i32) -> (i32, i32)
      scf.yield %a : i32
    } else {
      %b, %lb = "fcvd.hole"(%x) {sym_name = "B", leaks = 1 : i64} : (i32) -> (i32, i32)
      scf.yield %b : i32
    }
    func.return
  }

  func.func @target(%c: i1, %x: i32) {
    cf.cond_br %c, ^then, ^else
  ^then:
    %b, %lb = "fcvd.hole"(%x) {sym_name = "B", leaks = 1 : i64} : (i32) -> (i32, i32)
    cf.br ^join(%b : i32)
  ^else:
    %a, %la = "fcvd.hole"(%x) {sym_name = "A", leaks = 1 : i64} : (i32) -> (i32, i32)
    cf.br ^join(%a : i32)
  ^join(%r: i32):
    func.return
  }
}
