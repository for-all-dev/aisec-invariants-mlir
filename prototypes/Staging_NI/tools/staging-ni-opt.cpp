#include "stagingNI/Passes.h"

#include "mlir/Dialect/Affine/IR/AffineOps.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/SCF/IR/SCF.h"
#include "mlir/Dialect/Tensor/IR/Tensor.h"

#include "mlir/IR/DialectRegistry.h"
#include "mlir/Tools/mlir-opt/MlirOptMain.h"

using namespace mlir;

int main(int argc, char **argv) {

  DialectRegistry registry;

  registry.insert<
      func::FuncDialect,
      affine::AffineDialect,
      tensor::TensorDialect,
      arith::ArithDialect,
      scf::SCFDialect>();

  // Register your pass
  stagingni::registerPasses();

  return failed(MlirOptMain(
      argc,
      argv,
      "Staging Non-Interference Optimizer\n",
      registry));
}