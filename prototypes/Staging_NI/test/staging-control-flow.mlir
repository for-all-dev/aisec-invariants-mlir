// RUN: %staging-ni-opt --verify-staging-ni --verify-diagnostics --split-input-file %s

// scf.if: branching on a staging-tainted condition is itself a
// staging-time information flow, distinct from loop bounds/addresses --
// previously unchecked entirely (no visitor existed for it at all).

func.func @scf_if_condition(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  %cond = arith.cmpi eq, %dim, %c0 : index
  // expected-error @+1 {{branch condition depends on protected runtime data}}
  scf.if %cond {
    scf.yield
  }
  return
}

// -----

// scf.while: the condition is produced by scf.condition in the "before"
// region, not on scf.while itself.

func.func @scf_while_condition(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  scf.while (%arg = %dim) : (index) -> index {
    %cond = arith.cmpi sgt, %arg, %c0 : index
    // expected-error @+1 {{scf.while condition depends on protected runtime data}}
    scf.condition(%cond) %arg : index
  } do {
  ^bb0(%arg : index):
    scf.yield %c0 : index
  }
  return
}
