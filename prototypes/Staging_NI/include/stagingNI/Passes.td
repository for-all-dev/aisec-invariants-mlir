//===- Passes.td ----------------------------------------------*- tablegen -*-===//
//
// Pass definitions for the Staging Non-Interference project.
//
//===----------------------------------------------------------------------===//

#ifndef STAGINGNI_PASSES
#define STAGINGNI_PASSES

include "mlir/Pass/PassBase.td"

def VerifyStagingNonInterference
    : Pass<"verify-staging-ni", "func::FuncOp"> {

  let summary = "Verify staging-time non-interference";

  let description = [{
    Verifies that compiler staging decisions do not depend on
    protected information.

    The pass performs a forward taint analysis with two taint domains:

      • Runtime Taint
          Tracks protected tensor values.

      • Staging Taint
          Tracks index values derived from protected tensors
          (e.g. tensor.dim).

    Violations are reported when staging-tainted values influence:

      * affine.for loop bounds
      * scf.for loop bounds
      * affine.load addresses
      * affine.store addresses
      * scf.if / scf.while branch conditions (staging-time control flow)

    A construct this analysis does not model (block arguments other than
    loop induction vars/iter_args, secret.generic region bodies, ...) is
    reported as UNKNOWN rather than silently treated as safe.
  }];

  let dependentDialects = [
    "mlir::affine::AffineDialect",
    "mlir::arith::ArithDialect",
    "mlir::func::FuncDialect",
    "mlir::scf::SCFDialect",
    "mlir::tensor::TensorDialect",
  ];
}

#endif // STAGINGNI_PASSES