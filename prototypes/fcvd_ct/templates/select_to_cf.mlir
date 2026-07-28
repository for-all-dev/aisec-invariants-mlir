// Turning a branchless select into a branch -- if-conversion run backwards, which
// is what a "lower select to control flow" step does on targets without cmov.
//
// Expected: CT-BREAKING. The source makes no observation at all; the target
// observes the condition, so two inputs that were indistinguishable stop being so.
// This is the static counterpart of the `select` kernels `mlir_leak` probes by
// measurement.
builtin.module {
  func.func @source(%c: i1, %x: i32, %y: i32) {
    %r = arith.select %c, %x, %y : i32
    func.return
  }

  func.func @target(%c: i1, %x: i32, %y: i32) {
    cf.cond_br %c, ^then, ^else
  ^then:
    cf.br ^join(%x : i32)
  ^else:
    cf.br ^join(%y : i32)
  ^join(%r: i32):
    func.return
  }
}
