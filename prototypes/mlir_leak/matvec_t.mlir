// matvec_t: tensor-typed matvec (for the one-shot-bufferization pipeline P4).
// Same computation as matvec.mlir but on tensors + a returned result, so
// bufferization has real work to do (alloc/copy/in-place decisions). After
// --buffer-results-to-out-params the ABI is void @matvec_t(W, x, out).
func.func @matvec_t(%W: tensor<256x256xf32>, %x: tensor<256xf32>) -> tensor<256xf32> {
  %z = arith.constant 0.0 : f32
  %e = tensor.empty() : tensor<256xf32>
  %f = linalg.fill ins(%z : f32) outs(%e : tensor<256xf32>) -> tensor<256xf32>
  %y = linalg.matvec ins(%W, %x : tensor<256x256xf32>, tensor<256xf32>)
                     outs(%f : tensor<256xf32>) -> tensor<256xf32>
  return %y : tensor<256xf32>
}
