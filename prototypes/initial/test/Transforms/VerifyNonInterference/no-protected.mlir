// RUN: %aisec-opt --aisec-verify-non-interference %s | FileCheck %s

// A function with a secret-typed argument that is NOT tagged `aisec.protected`.
// The verifier should not emit any diagnostic, regardless of what the body does
// with the secret. This test confirms the pass is inert in the absence of a
// protection annotation.

// CHECK-LABEL: func.func @no_protected
func.func @no_protected(%w: !secret.secret<tensor<3x3xf32>>)
    -> !secret.secret<tensor<3x3xf32>> {
  return %w : !secret.secret<tensor<3x3xf32>>
}
