// RUN: %aisec-opt --aisec-verify-non-interference --verify-diagnostics --split-input-file %s

// Affine-flow check. A protected secret used by two
// distinct downstream consumers is a fan-out leak — even when both consumers
// are individually-sanctioned declassifications, splitting the same secret
// across two channels gives an attacker two correlated outputs to triangulate
// from. The verifier rejects multi-use of any `aisec.protected` argument.

// -----

// NEGATIVE CASE: protected weight is used by two `secret.reveal` ops, each
// individually tagged `aisec.declassify`. The non-interference check would
// not catch this (each reveal in isolation is well-formed), but the affine
// check does.

func.func @fanout_via_two_reveals(
    %w: !secret.secret<tensor<3x3xf32>> {aisec.protected}
) -> (tensor<3x3xf32>, tensor<3x3xf32>) {
  // expected-error @+0 {{has 2 direct uses; affine flow requires at most one}}
  %r1 = secret.reveal %w {aisec.declassify}
      : !secret.secret<tensor<3x3xf32>> -> tensor<3x3xf32>
  %r2 = secret.reveal %w {aisec.declassify}
      : !secret.secret<tensor<3x3xf32>> -> tensor<3x3xf32>
  return %r1, %r2 : tensor<3x3xf32>, tensor<3x3xf32>
}

// -----

// NEGATIVE CASE: protected weight is fed into two distinct `secret.generic`
// regions. Each generic individually does fine work; the leak is the fact
// that the same weight is the *source* of both. Affine check catches it.

func.func @fanout_via_two_generics(
    %w: !secret.secret<tensor<3x3xf32>> {aisec.protected}
) -> tensor<3x3xf32> {
  // expected-error @+0 {{has 2 direct uses; affine flow requires at most one}}
  %a = secret.generic(%w: !secret.secret<tensor<3x3xf32>>) {
    ^bb0(%cleartext: tensor<3x3xf32>):
      %sum = arith.addf %cleartext, %cleartext : tensor<3x3xf32>
      secret.yield %sum : tensor<3x3xf32>
  } -> !secret.secret<tensor<3x3xf32>>
  %b = secret.generic(%w: !secret.secret<tensor<3x3xf32>>) {
    ^bb0(%cleartext: tensor<3x3xf32>):
      %neg = arith.negf %cleartext : tensor<3x3xf32>
      secret.yield %neg : tensor<3x3xf32>
  } -> !secret.secret<tensor<3x3xf32>>
  %ra = secret.reveal %a {aisec.declassify}
      : !secret.secret<tensor<3x3xf32>> -> tensor<3x3xf32>
  %rb = secret.reveal %b {aisec.declassify}
      : !secret.secret<tensor<3x3xf32>> -> tensor<3x3xf32>
  %sum = arith.addf %ra, %rb : tensor<3x3xf32>
  return %sum : tensor<3x3xf32>
}

// -----

// POSITIVE CASE: protected weight is used by exactly one downstream consumer
// (a single `secret.generic`), which itself uses the cleartext block arg
// internally many times. Internal multi-use inside the generic body is
// allowed — the affine constraint is on the *protected function argument*'s
// direct uses, not on uses of the cleartext block arg.

func.func @internal_multi_use_ok(
    %w: !secret.secret<tensor<3x3xf32>> {aisec.protected}
) -> tensor<3x3xf32> {
  %out = secret.generic(%w: !secret.secret<tensor<3x3xf32>>) {
    ^bb0(%cleartext: tensor<3x3xf32>):
      // Cleartext block arg is used four times here — that's fine,
      // because all the use is inside one secret.generic region (one
      // direct use of %w at the function level).
      %a = arith.addf %cleartext, %cleartext : tensor<3x3xf32>
      %b = arith.mulf %cleartext, %a : tensor<3x3xf32>
      %c = arith.subf %b, %cleartext : tensor<3x3xf32>
      secret.yield %c : tensor<3x3xf32>
  } -> !secret.secret<tensor<3x3xf32>>
  %r = secret.reveal %out {aisec.declassify}
      : !secret.secret<tensor<3x3xf32>> -> tensor<3x3xf32>
  return %r : tensor<3x3xf32>
}
