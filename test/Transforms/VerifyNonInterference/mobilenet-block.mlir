// RUN: %aisec-opt --aisec-verify-non-interference --verify-diagnostics --split-input-file %s | FileCheck %s

// End-to-end demo: a MobileNetV2-style inverted residual block with all
// convolution weights marked `!secret.secret<...>` + `{aisec.protected}`.
//
// This file is NOT produced by torch-mlir — it is a hand-written
// linalg-on-tensors approximation of the block shape. The verifier only cares
// about dataflow (who uses what, where the reveal is), not about faithful
// ML-op semantics, so the ops inside the `secret.generic` are illustrative.
//
// Shapes (chosen small enough to be readable; not the real MobileNetV2 values):
//   input activation: 1 x 16 x 8 x 8  (NCHW, public)
//   expand   weights: 96 x 16 x 1 x 1 (1x1 conv, secret, protected)
//   depthwise weights: 96 x 1 x 3 x 3 (3x3 dw conv, secret, protected)
//   project  weights: 24 x 96 x 1 x 1 (1x1 conv, secret, protected)
//   output activation: 1 x 24 x 8 x 8 (public, after sanctioned declassify)

// -----

// POSITIVE CASE: declassification at the sanctioned egress point.
// The verifier should accept this.

// CHECK-LABEL: func.func @mobilenet_block_sanctioned
func.func @mobilenet_block_sanctioned(
    %input: tensor<1x16x8x8xf32>,
    %w_expand:    !secret.secret<tensor<96x16x1x1xf32>> {aisec.protected},
    %w_depthwise: !secret.secret<tensor<96x1x3x3xf32>>  {aisec.protected},
    %w_project:   !secret.secret<tensor<24x96x1x1xf32>> {aisec.protected}
) -> tensor<1x24x8x8xf32> {
  // Lift the whole inference pipeline into a single secret.generic region.
  // The block args are the cleartext views of each secret operand.
  %out_secret = secret.generic(
      %w_expand    : !secret.secret<tensor<96x16x1x1xf32>>,
      %w_depthwise : !secret.secret<tensor<96x1x3x3xf32>>,
      %w_project   : !secret.secret<tensor<24x96x1x1xf32>>
  ) {
    ^bb0(
        %we: tensor<96x16x1x1xf32>,
        %wd: tensor<96x1x3x3xf32>,
        %wp: tensor<24x96x1x1xf32>
    ):
      // Buffers to write into (would be init tensors in a real lowering).
      %empty_expand = tensor.empty() : tensor<1x96x8x8xf32>
      %empty_dw     = tensor.empty() : tensor<1x96x8x8xf32>
      %empty_proj   = tensor.empty() : tensor<1x24x8x8xf32>

      // Expand 1x1 conv
      %expanded = linalg.conv_2d_nchw_fchw
          ins(%input, %we : tensor<1x16x8x8xf32>, tensor<96x16x1x1xf32>)
          outs(%empty_expand : tensor<1x96x8x8xf32>)
          -> tensor<1x96x8x8xf32>

      // Depthwise 3x3 conv (stride 1, padding implied by shapes for the demo).
      %dw = linalg.depthwise_conv_2d_nchw_chw
          ins(%expanded, %wd : tensor<1x96x8x8xf32>, tensor<96x1x3x3xf32>)
          outs(%empty_dw : tensor<1x96x8x8xf32>)
          -> tensor<1x96x8x8xf32>

      // Project 1x1 conv
      %proj = linalg.conv_2d_nchw_fchw
          ins(%dw, %wp : tensor<1x96x8x8xf32>, tensor<24x96x1x1xf32>)
          outs(%empty_proj : tensor<1x24x8x8xf32>)
          -> tensor<1x24x8x8xf32>

      secret.yield %proj : tensor<1x24x8x8xf32>
  } -> !secret.secret<tensor<1x24x8x8xf32>>

  // Sanctioned declassification: activation exits the secret domain at a
  // single, explicitly-tagged egress op.
  %out = secret.reveal %out_secret {aisec.declassify}
      : !secret.secret<tensor<1x24x8x8xf32>> -> tensor<1x24x8x8xf32>
  return %out : tensor<1x24x8x8xf32>
}

// -----

// NEGATIVE CASE: same block, but the reveal is missing `{aisec.declassify}`.
// The verifier must reject.

func.func @mobilenet_block_leak(
    %input: tensor<1x16x8x8xf32>,
    %w_expand:    !secret.secret<tensor<96x16x1x1xf32>> {aisec.protected},
    %w_depthwise: !secret.secret<tensor<96x1x3x3xf32>>  {aisec.protected},
    %w_project:   !secret.secret<tensor<24x96x1x1xf32>> {aisec.protected}
) -> tensor<1x24x8x8xf32> {
  %out_secret = secret.generic(
      %w_expand    : !secret.secret<tensor<96x16x1x1xf32>>,
      %w_depthwise : !secret.secret<tensor<96x1x3x3xf32>>,
      %w_project   : !secret.secret<tensor<24x96x1x1xf32>>
  ) {
    ^bb0(
        %we: tensor<96x16x1x1xf32>,
        %wd: tensor<96x1x3x3xf32>,
        %wp: tensor<24x96x1x1xf32>
    ):
      %empty_expand = tensor.empty() : tensor<1x96x8x8xf32>
      %empty_dw     = tensor.empty() : tensor<1x96x8x8xf32>
      %empty_proj   = tensor.empty() : tensor<1x24x8x8xf32>
      %expanded = linalg.conv_2d_nchw_fchw
          ins(%input, %we : tensor<1x16x8x8xf32>, tensor<96x16x1x1xf32>)
          outs(%empty_expand : tensor<1x96x8x8xf32>)
          -> tensor<1x96x8x8xf32>
      %dw = linalg.depthwise_conv_2d_nchw_chw
          ins(%expanded, %wd : tensor<1x96x8x8xf32>, tensor<96x1x3x3xf32>)
          outs(%empty_dw : tensor<1x96x8x8xf32>)
          -> tensor<1x96x8x8xf32>
      %proj = linalg.conv_2d_nchw_fchw
          ins(%dw, %wp : tensor<1x96x8x8xf32>, tensor<24x96x1x1xf32>)
          outs(%empty_proj : tensor<1x24x8x8xf32>)
          -> tensor<1x24x8x8xf32>
      secret.yield %proj : tensor<1x24x8x8xf32>
  } -> !secret.secret<tensor<1x24x8x8xf32>>

  // expected-error @+1 {{protected secret revealed without declassification}}
  %out = secret.reveal %out_secret
      : !secret.secret<tensor<1x24x8x8xf32>> -> tensor<1x24x8x8xf32>
  return %out : tensor<1x24x8x8xf32>
}
