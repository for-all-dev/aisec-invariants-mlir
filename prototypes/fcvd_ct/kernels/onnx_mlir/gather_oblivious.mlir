// The same gather written obliviously: every position of `data` is read, and the one
// that matches is kept with an `arith.select`. This is what HEIR's
// `--convert-secret-extract-to-static-extract` produces automatically.
//
// onnx-mlir has no such pass -- there is no data-oblivious mode in
// src/Compiler/CompilerPasses.cpp -- so this form has to be written by hand, and that
// is the finding rather than the kernel itself.
//
// Expected: SECURE, with the address observations proved equal rather than absent.
func.func @gather_oblivious(%data: memref<8xi8>, %index: index {fcvdct.secret}, %out: memref<2xi8>) {
  %zero = arith.constant 0 : i8
  affine.for %j = 0 to 2 {
    %element = affine.for %i = 0 to 8 iter_args(%acc = %zero) -> (i8) {
      %candidate = memref.load %data[%i] : memref<8xi8>
      %matches = arith.cmpi eq, %i, %index : index
      %kept = arith.select %matches, %candidate, %acc : i8
      affine.yield %kept : i8
    }
    memref.store %element, %out[%j] : memref<2xi8>
    affine.yield
  }
  func.return
}
