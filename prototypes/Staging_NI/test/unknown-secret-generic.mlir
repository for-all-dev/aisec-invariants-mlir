// RUN: %staging-ni-opt --verify-staging-ni --verify-diagnostics --allow-unregistered-dialect --split-input-file %s

// secret.generic is not in this project's dialect registry (it lives in
// HEIR's Secret dialect, a separate Bazel-built subproject under
// prototypes/initial). Modeled here as an unregistered op via
// -allow-unregistered-dialect so the UNKNOWN path can be exercised without
// pulling in that dependency. A tainted operand reaching an unmodeled
// region body must be reported as UNKNOWN -- NOT silently treated as safe,
// which was the previous (unsound) behavior for any construct this walker
// doesn't understand.

func.func @secret_generic_with_tainted_operand(
    %A : tensor<?xf32> {stagingni.protected}
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  // expected-remark @+1 {{secret.generic region body is not modeled}}
  "secret.generic"(%dim) ({
  ^bb0(%x: index):
    "secret.yield"(%x) : (index) -> ()
  }) : (index) -> ()
  return
}

// -----

// Negative control: secret.generic with no tainted operand at all must stay
// silent -- UNKNOWN is about a tainted value reaching an unmodeled
// construct, not about the construct's mere presence.

func.func @secret_generic_no_tainted_operand(
    %A : tensor<?xf32>
) {
  %c0 = arith.constant 0 : index
  %dim = tensor.dim %A, %c0 : tensor<?xf32>
  "secret.generic"(%dim) ({
  ^bb0(%x: index):
    "secret.yield"(%x) : (index) -> ()
  }) : (index) -> ()
  return
}
