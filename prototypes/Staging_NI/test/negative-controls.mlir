// RUN: %staging-ni-opt --verify-staging-ni --verify-diagnostics --split-input-file %s

// No `stagingni.protected` attribute anywhere: seedRuntimeTaint finds
// nothing, so nothing downstream can ever be flagged. Must produce zero
// diagnostics (an empty --verify-diagnostics run succeeds iff no
// unexpected diagnostic fires).

func.func @no_protected_attr(
    %A : tensor<?xf32>
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  affine.for %i = 0 to %dim {
  }
  return
}

// -----

// A protected tensor is present, but the loop bound is an unrelated
// compile-time constant: the checker must not flag a construct merely
// because a protected value exists SOMEWHERE in the function.

func.func @protected_present_but_unrelated_bound(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c10 = arith.constant 10 : index
  affine.for %i = 0 to %c10 {
  }
  return
}

// -----

// Multi-use inside a single arithmetic expression is fine as long as no
// staging-tainted value reaches a checked sink.

func.func @staging_taint_that_never_reaches_a_sink(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  %c1 = arith.constant 1 : index
  %unused = arith.addi %dim, %c1 : index
  return
}
