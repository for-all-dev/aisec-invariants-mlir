// HEIR, stage 0: the input of `--convert-secret-extract-to-static-extract`, from that
// pass's own test (tests/Transforms/convert_secret_extract_to_static_extract/
// secret_extracts.mlir, @extract_at_secret_index), with the `secret.generic` wrapper
// dropped -- the pass rewrites the body, not the wrapper -- and the tensor shortened
// from 32 to 8 so the hardened form can be unrolled exactly.
//
// The secret marking is HEIR's own `{secret.secret}`, as `--secretize` writes it.
//
// Expected: INSECURE on `address`.
func.func @extract_at_secret_index(%t: tensor<8xi16>, %index: index {secret.secret}) -> i16 {
  %extracted = tensor.extract %t[%index] : tensor<8xi16>
  func.return %extracted : i16
}
