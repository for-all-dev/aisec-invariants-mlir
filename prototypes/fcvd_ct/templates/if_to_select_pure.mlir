// If-conversion in the hardening direction: a branch over *pure* code becomes a
// select. Both arms are computed unconditionally in the target, which is exactly what
// makes the branch disappear.
//
// Expected: CT-PRESERVING -- the lowering removes an observation (the condition) and
// adds none, which the property allows.
builtin.module {
  func.func @source(%c: i1, %x: i32) {
    %r = scf.if %c -> (i32) {
      %a = "fcvd.hole"(%x) {sym_name = "A", leaks = 0 : i64} : (i32) -> i32
      scf.yield %a : i32
    } else {
      %b = "fcvd.hole"(%x) {sym_name = "B", leaks = 0 : i64} : (i32) -> i32
      scf.yield %b : i32
    }
    func.return
  }

  func.func @target(%c: i1, %x: i32) {
    %a = "fcvd.hole"(%x) {sym_name = "A", leaks = 0 : i64} : (i32) -> i32
    %b = "fcvd.hole"(%x) {sym_name = "B", leaks = 0 : i64} : (i32) -> i32
    %r = arith.select %c, %a, %b : i32
    func.return
  }
}
