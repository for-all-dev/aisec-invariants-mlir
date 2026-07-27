#ifndef STAGINGNI_PASSES_H
#define STAGINGNI_PASSES_H

#include "mlir/Dialect/Affine/IR/AffineOps.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/SCF/IR/SCF.h"
#include "mlir/Dialect/Tensor/IR/Tensor.h"
#include "mlir/Pass/Pass.h"

namespace mlir {
namespace stagingni {

#define GEN_PASS_DECL
#include "stagingNI/Passes.h.inc"

#define GEN_PASS_REGISTRATION
#include "stagingNI/Passes.h.inc"

} // namespace stagingni
} // namespace mlir

#endif