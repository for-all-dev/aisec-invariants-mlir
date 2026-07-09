// mask_select_t: tensor-typed branchless select (for the bufferization pipeline P4).
// Same computation as select.mlir but on tensors + a returned result. After
// --buffer-results-to-out-params the ABI is void @mask_select_t(mask, a, b, out).
#id = affine_map<(d0) -> (d0)>
func.func @mask_select_t(%mask: tensor<4096xi8>,
                         %a: tensor<4096xf32>, %b: tensor<4096xf32>) -> tensor<4096xf32> {
  %e = tensor.empty() : tensor<4096xf32>
  %o = linalg.generic {
    indexing_maps = [#id, #id, #id, #id],
    iterator_types = ["parallel"]
  } ins(%mask, %a, %b : tensor<4096xi8>, tensor<4096xf32>, tensor<4096xf32>)
    outs(%e : tensor<4096xf32>) {
  ^bb0(%m: i8, %av: f32, %bv: f32, %oo: f32):
    %zc = arith.constant 0 : i8
    %c = arith.cmpi ne, %m, %zc : i8
    %s = arith.select %c, %av, %bv : f32
    linalg.yield %s : f32
  } -> tensor<4096xf32>
  return %o : tensor<4096xf32>
}
