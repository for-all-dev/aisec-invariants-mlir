// RUN: %aisec-opt --aisec-verify-non-interference --verify-diagnostics %s | FileCheck %s

// A protected secret argument is revealed at a sink that is EXPLICITLY tagged
// with `aisec.declassify`. The verifier must accept this — it is the sanctioned
// escape hatch.

// CHECK-LABEL: func.func @sanctioned_declassify
func.func @sanctioned_declassify(
    %w: !secret.secret<tensor<3x3xf32>> {aisec.protected}
) -> tensor<3x3xf32> {
  %r = secret.reveal %w {aisec.declassify}
      : !secret.secret<tensor<3x3xf32>> -> tensor<3x3xf32>
  return %r : tensor<3x3xf32>
}
