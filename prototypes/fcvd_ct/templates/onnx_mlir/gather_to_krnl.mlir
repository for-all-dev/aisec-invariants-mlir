// onnx-mlir `--convert-onnx-to-krnl` for `onnx.Gather`, transcribed from the pattern
// that emits it (src/Conversion/ONNXToKrnl/Tensor/Gather.cpp:104-144): a loop over the
// output, which loads an index out of `indices`, then loads `data` at that index, then
// stores the element.
//
// The source is a hole with no leakage, and that is the honest reading of the ONNX
// level: `onnx.Gather` is a tensor-valued operation with no memory and no timing
// meaning attached to it. The target is memory, and the address it touches is the value
// that was loaded from `indices`.
//
// Expected: CT-BREAKING (0 -> 3). If the gathered indices are private -- token ids in
// an embedding lookup are the ordinary case -- the lowering turns them into addresses.
// onnx-mlir has no pass that hardens this, which is the difference from HEIR: there,
// `--convert-secret-extract-to-static-extract` exists for exactly this shape.
builtin.module {
  func.func @source(%data: memref<8xi8>, %indices: memref<2xi8>, %out: memref<2xi8>) {
    %gathered = "fcvd.hole"() {sym_name = "gather", leaks = 0 : i64} : () -> i8
    func.return
  }

  func.func @target(%data: memref<8xi8>, %indices: memref<2xi8>, %out: memref<2xi8>) {
    %j = arith.constant 0 : index
    %index_value = memref.load %indices[%j] : memref<2xi8>
    %index = arith.index_cast %index_value : i8 to index
    %element = memref.load %data[%index] : memref<8xi8>
    memref.store %element, %out[%j] : memref<2xi8>
    func.return
  }
}
