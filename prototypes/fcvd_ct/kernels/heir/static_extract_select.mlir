// HEIR, stage 2: the same code after `--convert-if-to-select`, the last pass of
// `--convert-to-data-oblivious` (lib/Pipelines/PipelineRegistration.cpp:163). The
// branch becomes an `arith.select`, which is what finally removes the control channel.
//
// The pass refuses to do this when an arm contains code that cannot be speculated --
// its own diagnostic is "Cannot convert scf.if to arith.select, as it contains code
// that cannot be safely hoisted" -- and templates/heir/if_to_select_speculative.mlir is
// where that side condition is checked rather than taken on trust.
//
// Expected: SECURE on every obligation. This is the end state the pipeline promises.
func.func @extract_at_secret_index(%t: tensor<8xi16>, %index: index {secret.secret}) -> i16 {
  %c0 = arith.constant 0 : index
  %init = tensor.extract %t[%c0] : tensor<8xi16>
  %result = affine.for %i = 0 to 8 iter_args(%acc = %init) -> (i16) {
    %matches = arith.cmpi eq, %i, %index : index
    %candidate = tensor.extract %t[%i] : tensor<8xi16>
    %kept = arith.select %matches, %candidate, %acc : i16
    affine.yield %kept : i16
  }
  func.return %result : i16
}
