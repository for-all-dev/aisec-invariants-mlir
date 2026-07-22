module {

func.func @foo(%A : memref<?xf32>,
               %T : tensor<?xf32>) {

  %c0 = arith.constant 0 : index

  %dim = tensor.dim %T, %c0 : tensor<?xf32>

  %v = arith.constant 1.0 : f32

  affine.store %v, %A[%dim] : memref<?xf32>

  return
}

}