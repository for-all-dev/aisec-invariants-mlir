func.func @dynshape_t(%kbuf: tensor<1xi32>) -> tensor<1xf32> {
  %c0 = arith.constant 0 : index
  %k32 = tensor.extract %kbuf[%c0] : tensor<1xi32>
  %k = arith.index_cast %k32 : i32 to index
  %one = arith.constant 1.0 : f32
  %z = arith.constant 0.0 : f32
  %e = tensor.empty(%k) : tensor<?xf32>
  %f = linalg.fill ins(%one : f32) outs(%e : tensor<?xf32>) -> tensor<?xf32>
  %init = tensor.empty() : tensor<1xf32>
  %fi = linalg.fill ins(%z : f32) outs(%init : tensor<1xf32>) -> tensor<1xf32>
  %r = linalg.generic {indexing_maps = [affine_map<(d0)->(d0)>, affine_map<(d0)->(0)>], iterator_types = ["reduction"]}
       ins(%f : tensor<?xf32>) outs(%fi : tensor<1xf32>) {
  ^bb0(%x: f32, %acc: f32):
    %a = arith.addf %acc, %x : f32
    linalg.yield %a : f32
  } -> tensor<1xf32>
  return %r : tensor<1xf32>
}
