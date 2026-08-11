// Coverage control: `cf.switch` is not modelled. The answer must be UNKNOWN, not a
// verdict about the part of the program that happened to be understood. (This control
// used `scf.while` until 2026-08-09, when `scf.while` gained bounded unrolling for the
// Polygeist `--loop-restructure` step; `cf.switch` keeps the role.)
builtin.module {
  func.func @source(%x: i32) {
    cf.switch %x : i32, [
      default: ^bb1,
      0: ^bb2
    ]
  ^bb1:
    %a = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 0 : i64} : (i32) -> i32
    func.return
  ^bb2:
    func.return
  }

  func.func @target(%x: i32) {
    cf.switch %x : i32, [
      default: ^bb1,
      0: ^bb2
    ]
  ^bb1:
    %a = "fcvd.hole"(%x) {sym_name = "BODY", leaks = 0 : i64} : (i32) -> i32
    func.return
  ^bb2:
    func.return
  }
}
