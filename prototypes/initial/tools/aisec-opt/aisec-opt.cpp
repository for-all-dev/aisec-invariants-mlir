//===- aisec-opt.cpp - aisec MLIR optimizer driver ------------*- C++ -*-===//
//
// Minimal mlir-opt-style driver that registers:
//   * upstream MLIR dialects
//   * HEIR's `secret` dialect
//   * our aisec transform passes
//
// Usage:
//   aisec-opt --aisec-verify-non-interference input.mlir
//
//===----------------------------------------------------------------------===//

#include "AISec/Transforms/Passes.h"

#include "lib/Dialect/Secret/IR/SecretDialect.h"

#include "mlir/IR/DialectRegistry.h"
#include "mlir/InitAllDialects.h"
#include "mlir/InitAllPasses.h"
#include "mlir/Tools/mlir-opt/MlirOptMain.h"

int main(int argc, char **argv) {
  mlir::DialectRegistry registry;

  // Upstream dialects (func, arith, tensor, linalg, ...).
  mlir::registerAllDialects(registry);

  // HEIR's secret dialect — the foundation we build on.
  registry.insert<mlir::heir::secret::SecretDialect>();

  // Upstream passes, plus ours.
  mlir::registerAllPasses();
  mlir::aisec::registerAISecPasses();

  return mlir::asMainReturnCode(
      mlir::MlirOptMain(argc, argv, "aisec-opt — non-interference verifier\n",
                        registry));
}
