// RUN: %aisec-opt --aisec-verify-non-interference --verify-diagnostics --split-input-file %s

// A protected secret argument is revealed without the `aisec.declassify` marker.
// The verifier must reject.

func.func @direct_leak(
    %w: !secret.secret<tensor<3x3xf32>> {aisec.protected}
) -> tensor<3x3xf32> {
  // expected-error @+1 {{protected secret revealed without declassification}}
  %r = secret.reveal %w : !secret.secret<tensor<3x3xf32>> -> tensor<3x3xf32>
  return %r : tensor<3x3xf32>
}

// -----

// A leak that occurs after routing through a secret.generic region. Taint must
// propagate through the generic's operand→block-arg and body→result edges.

func.func @leak_after_generic(
    %w: !secret.secret<tensor<3x3xf32>> {aisec.protected}
) -> tensor<3x3xf32> {
  %doubled = secret.generic(%w: !secret.secret<tensor<3x3xf32>>) {
    ^bb0(%clear: tensor<3x3xf32>):
      %two = arith.addf %clear, %clear : tensor<3x3xf32>
      secret.yield %two : tensor<3x3xf32>
  } -> !secret.secret<tensor<3x3xf32>>
  // expected-error @+1 {{protected secret revealed without declassification}}
  %r = secret.reveal %doubled : !secret.secret<tensor<3x3xf32>> -> tensor<3x3xf32>
  return %r : tensor<3x3xf32>
}
