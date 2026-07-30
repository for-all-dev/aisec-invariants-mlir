// HEIR, stage 1: after `--convert-secret-extract-to-static-extract`, transcribed from
// the pattern that emits it (lib/Transforms/ConvertSecretExtractToStaticExtract/
// ConvertSecretExtractToStaticExtract.cpp:71-140): an extract at index 0 for the
// initial value, then every index visited in turn, keeping the one that matches.
//
// The address channel is closed -- every extraction is at a public index -- but the
// `scf.if` is still a branch on a secret-derived condition, which is why HEIR's own
// pipeline runs `--convert-if-to-select` afterwards (tools/heir-opt.cpp:613).
//
// Expected: INSECURE on `control`, and SECURE on `address`.
func.func @extract_at_secret_index(%t: tensor<8xi16>, %index: index {secret.secret}) -> i16 {
  %c0 = arith.constant 0 : index
  %init = tensor.extract %t[%c0] : tensor<8xi16>
  %result = affine.for %i = 0 to 8 iter_args(%acc = %init) -> (i16) {
    %matches = arith.cmpi eq, %i, %index : index
    %candidate = tensor.extract %t[%i] : tensor<8xi16>
    %kept = scf.if %matches -> (i16) {
      scf.yield %candidate : i16
    } else {
      scf.yield %acc : i16
    }
    affine.yield %kept : i16
  }
  func.return %result : i16
}
