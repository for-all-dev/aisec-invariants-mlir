// RUN: %staging-ni-opt --verify-staging-ni --verify-diagnostics --split-input-file %s

// The readme's own worked example: a protected tensor's dim() feeds an
// affine.for bound directly (through one arith.addi). Positive case.

func.func @direct_dim_via_addi(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  %c1 = arith.constant 1 : index
  %bound = arith.addi %dim, %c1 : index
  // expected-error @+1 {{loop upper bound depends on protected runtime data}}
  affine.for %i = 0 to %bound {
  }
  return
}

// -----

// tensor.dim used AS the bound with no arithmetic in between: the direct
// case, not the derived one.

func.func @direct_dim_no_arithmetic(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  // expected-error @+1 {{loop upper bound depends on protected runtime data}}
  affine.for %i = 0 to %dim {
  }
  return
}

// -----

// A longer arithmetic chain (mul then sub): staging taint must survive more
// than one hop through the supported arith ops.

func.func @multi_hop_arithmetic_chain(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  %c2 = arith.constant 2 : index
  %scaled = arith.muli %dim, %c2 : index
  %c1 = arith.constant 1 : index
  %bound = arith.subi %scaled, %c1 : index
  // expected-error @+1 {{loop upper bound depends on protected runtime data}}
  affine.for %i = 0 to %bound {
  }
  return
}

// -----

// affine.load/affine.store address, not just loop bounds.

func.func @load_store_address(
    %A : tensor<?xf32> {stagingni.protected},
    %M : memref<?xf32>
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  %v = arith.constant 1.0 : f32
  // expected-error @+1 {{affine.store address depends on protected runtime data}}
  affine.store %v, %M[%dim] : memref<?xf32>
  // expected-error @+1 {{affine.load address depends on protected runtime data}}
  %r = affine.load %M[%dim] : memref<?xf32>
  return
}
