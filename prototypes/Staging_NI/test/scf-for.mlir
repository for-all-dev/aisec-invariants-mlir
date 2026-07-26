// RUN: %staging-ni-opt --verify-staging-ni --verify-diagnostics --split-input-file %s

// scf.for's own bounds (lower/upper/step), not just affine.for's.

func.func @scf_for_upper_bound(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  // expected-error @+1 {{loop upper bound depends on protected runtime data}}
  scf.for %i = %c0 to %dim step %c1 {
  }
  return
}

// -----

func.func @scf_for_step(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %c10 = arith.constant 10 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  // expected-error @+1 {{loop step depends on protected runtime data}}
  scf.for %i = %c0 to %c10 step %dim {
  }
  return
}

// -----

// iter_args carrying taint into the loop body: previously a silent false
// negative (readme's "scf.for iter_args propagation" gap) -- the outer
// loop's bound is public, so only the iter_arg carries the tainted value in;
// a nested loop keyed on that iter_arg must still be flagged.

func.func @iter_arg_carries_taint_into_body(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %c10 = arith.constant 10 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  scf.for %i = %c0 to %c10 step %c1 iter_args(%acc = %dim) -> (index) {
    // expected-error @+1 {{loop upper bound depends on protected runtime data}}
    scf.for %j = %c0 to %acc step %c1 {
    }
    scf.yield %acc : index
  }
  return
}
