//===- Passes.td - aisec transform passes -----------------*- tablegen -*-===//
//
// Pass definitions for the aisec-invariants-mlir project.
//
//===----------------------------------------------------------------------===//

#ifndef AISEC_TRANSFORMS_PASSES_TD
#define AISEC_TRANSFORMS_PASSES_TD

include "mlir/Pass/PassBase.td"

def VerifyNonInterferencePass
    : Pass<"aisec-verify-non-interference", "mlir::func::FuncOp"> {
  let summary =
      "Verify no `aisec.protected` secret leaks via `secret.reveal` without "
      "declassification";

  let description = [{
    Two checks on every `func.func` argument tagged with the `aisec.protected`
    unit attribute (intended for ML model weight tensors typed as
    `!secret.secret<T>`):

    1. **Non-interference modulo declassification.** Walks forward from each
       protected argument through SSA uses, propagating taint through
       `secret.generic` body regions. Every `secret.reveal` op reached in
       this walk must be tagged with `aisec.declassify`, otherwise the pass
       emits an error pointing at the reveal op.

    2. **Affine flow.** Each protected argument must have at most one direct
       SSA user. Multi-use is rejected as a fan-out leak — splitting a
       secret across two downstream channels is the textbook amplification
       vector and is a leak even if every channel is individually
       declassified.

    Further planned extensions include output-reaching affine flow,
    bandwidth-bounded egress, op-whitelist egress, and integrity-verify
    dominance.
  }];

  let dependentDialects = [
    "mlir::func::FuncDialect",
    "mlir::heir::secret::SecretDialect",
  ];
}

#endif  // AISEC_TRANSFORMS_PASSES_TD
