// Coverage control: `scf.while` is not modelled. The answer must be UNKNOWN, not a
// verdict about the part of the program that happened to be understood.
builtin.module {
  func.func @source(%x: i32) {
    %r = scf.while (%arg = %x) : (i32) -> i32 {
      %zero = arith.constant 0 : i32
      %go = arith.cmpi ne, %arg, %zero : i32
      scf.condition(%go) %arg : i32
    } do {
    ^body(%arg2: i32):
      %a = "fcvd.hole"(%arg2) {sym_name = "BODY", leaks = 0 : i64} : (i32) -> i32
      scf.yield %a : i32
    }
    func.return
  }

  func.func @target(%x: i32) {
    %r = scf.while (%arg = %x) : (i32) -> i32 {
      %zero = arith.constant 0 : i32
      %go = arith.cmpi ne, %arg, %zero : i32
      scf.condition(%go) %arg : i32
    } do {
    ^body(%arg2: i32):
      %a = "fcvd.hole"(%arg2) {sym_name = "BODY", leaks = 0 : i64} : (i32) -> i32
      scf.yield %a : i32
    }
    func.return
  }
}
