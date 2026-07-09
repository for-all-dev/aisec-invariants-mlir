// matvec: y = W . x   (W:256x256, x:256, y:256)
// Data-oblivious negative control. Secret = W. Dense fixed-bound loops, so
// execution is identical for any W -> must read oblivious under every pipeline.
// linalg.matvec accumulates into `y`, so the driver zero-inits y before the call.
func.func @matvec(%W: memref<256x256xf32>,
                  %x: memref<256xf32>,
                  %y: memref<256xf32>) {
  linalg.matvec ins(%W, %x : memref<256x256xf32>, memref<256xf32>)
                outs(%y : memref<256xf32>)
  return
}
