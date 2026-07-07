//===- Passes.h - aisec transform pass registration ------------*- C++ -*-===//
//
// Declarations and registration hooks for the aisec transform passes.
//
//===----------------------------------------------------------------------===//

#ifndef AISEC_TRANSFORMS_PASSES_H
#define AISEC_TRANSFORMS_PASSES_H

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Pass/Pass.h"

namespace mlir::aisec {

#define GEN_PASS_DECL
#include "AISec/Transforms/Passes.h.inc"

#define GEN_PASS_REGISTRATION
#include "AISec/Transforms/Passes.h.inc"

}  // namespace mlir::aisec

#endif  // AISEC_TRANSFORMS_PASSES_H
