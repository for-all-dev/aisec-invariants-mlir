// The same if-conversion, but the arms leak (they touch memory, divide, whatever the
// leakage model counts). Now executing both arms unconditionally is not a hardening:
// the target performs the *untaken* arm's observations too.
//
// Expected: CT-BREAKING, and the counterexample is the interesting part -- two inputs
// on which the taken arm behaves identically while the untaken one does not.
//
// This is the case that shows the guards are doing real work: it differs from
// `if_to_select_pure` only in whether the holes leak, and the verdict flips.
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
    %a, %la = "fcvd.hole"(%x) {sym_name = "A", leaks = 1 : i64} : (i32) -> (i32, i32)
    %b, %lb = "fcvd.hole"(%x) {sym_name = "B", leaks = 1 : i64} : (i32) -> (i32, i32)
    %r = arith.select %c, %a, %b : i32
    func.return
  }
}
