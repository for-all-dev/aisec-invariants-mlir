#SV = #sparse_tensor.encoding<{ map = (d0) -> (d0 : compressed) }>
func.func @scatter(%vals: tensor<8xf32>, %pos: tensor<2xindex>, %crd: tensor<8xindex>) -> tensor<256xf32> {
  %s = sparse_tensor.assemble %vals, %pos, %crd
       : tensor<8xf32>, tensor<2xindex>, tensor<8xindex> to tensor<256xf32, #SV>
  %d = sparse_tensor.convert %s : tensor<256xf32, #SV> to tensor<256xf32>
  return %d : tensor<256xf32>
}
