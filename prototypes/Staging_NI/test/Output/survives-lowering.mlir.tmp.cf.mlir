module {
  func.func @branch_survives_scf_to_cf(%arg0: tensor<?xf32> {stagingni.protected}) {
    %c0 = arith.constant 0 : index
    %dim = tensor.dim %arg0, %c0 : tensor<?xf32>
    %0 = arith.cmpi eq, %dim, %c0 : index
    cf.cond_br %0, ^bb1, ^bb2
  ^bb1:  // pred: ^bb0
    cf.br ^bb2
  ^bb2:  // 2 preds: ^bb0, ^bb1
    return
  }
}

