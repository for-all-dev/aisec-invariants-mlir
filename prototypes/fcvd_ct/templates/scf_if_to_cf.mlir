// The `-convert-scf-to-cf` step, as a structural specification: a two-armed
// `scf.if` becomes a conditional branch to two blocks joining at a continuation.
// The arms are holes -- arbitrary code -- so a proof covers every program the
// lowering can be applied to.
//
// Expected: CT-PRESERVING. Both sides observe the same branch condition and the
// same arm leakage under the same guards; the lowering only changes the shape.
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
    %a, %la = "fcvd.hole"(%x) {sym_name = "A", leaks = 1 : i64} : (i32) -> (i32, i32)
    cf.br ^join(%a : i32)
  ^else:
    %b, %lb = "fcvd.hole"(%x) {sym_name = "B", leaks = 1 : i64} : (i32) -> (i32, i32)
    cf.br ^join(%b : i32)
  ^join(%r: i32):
    func.return
  }
}
