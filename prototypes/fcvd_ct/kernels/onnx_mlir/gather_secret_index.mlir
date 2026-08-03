// onnx-mlir, after `--convert-onnx-to-krnl` and `--convert-krnl-to-affine`: the gather
// loop of src/Conversion/ONNXToKrnl/Tensor/Gather.cpp:104-144, with `krnl.iterate`
// already lowered to `affine.for` and `krnl.load` to `memref.load`
// (src/Compiler/CompilerPasses.cpp:310).
//
// Transcription note: in the real lowering the index is loaded out of the `indices`
// memref; here it is a secret argument, which is the same thing for this property --
// what matters is that the address of the `data` access is a private value. An
// embedding lookup on private token ids is the ordinary case.
//
// Expected: INSECURE on `address`.
func.func @gather(%data: memref<8xi8>, %index: index {fcvdct.secret}, %out: memref<2xi8>) {
  affine.for %j = 0 to 2 {
    %element = memref.load %data[%index] : memref<8xi8>
    memref.store %element, %out[%j] : memref<2xi8>
    affine.yield
  }
  func.return
}
