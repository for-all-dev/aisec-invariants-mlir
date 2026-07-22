#include "stagingNI/Passes.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/Operation.h"
#include "mlir/IR/Value.h"
#include "mlir/Pass/Pass.h"
#include "llvm/Support/raw_ostream.h"
#include "mlir/Dialect/Tensor/IR/Tensor.h"
#include "llvm/ADT/DenseSet.h"
#include "mlir/Dialect/Affine/IR/AffineOps.h"
#include "mlir/Dialect/SCF/IR/SCF.h"

using namespace mlir;

namespace mlir {
namespace stagingni {
class VerifyStagingNonInterferencePass
    : public PassWrapper<
          VerifyStagingNonInterferencePass,
          OperationPass<func::FuncOp>> {

public:
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(
      VerifyStagingNonInterferencePass)

  StringRef getArgument() const final {
    return "verify-staging-ni";
  }

  StringRef getDescription() const final {
    return "Verify staging-time non-interference";
  }

  void runOnOperation() override {

    func::FuncOp func = getOperation();

    runtimeTainted.clear();
    stagingTainted.clear();

    seedRuntimeTaint(func);

    func.walk([&](Operation *op) {
      visitOperation(op);
    });

    printSummary();
  }

private:

  //------------------------------------------------------------
  // Two taint domains
  //------------------------------------------------------------

  llvm::DenseSet<Value> runtimeTainted;
  llvm::DenseSet<Value> stagingTainted;

  //------------------------------------------------------------
  // Seed runtime taint
  //------------------------------------------------------------

  static constexpr StringLiteral kProtectedAttr = "stagingni.protected";

void seedRuntimeTaint(func::FuncOp func) {

  llvm::errs() << "\n=== Runtime Sources ===\n";

  for (auto [index, arg] : llvm::enumerate(func.getArguments())) {

    // Only protected arguments become runtime sources.
    if (!func.getArgAttr(index, kProtectedAttr))
      continue;

    runtimeTainted.insert(arg);

    llvm::errs() << "Runtime source : ";
    arg.print(llvm::errs());
    llvm::errs() << "\n";
  }
}

  //------------------------------------------------------------
  // tensor.dim
  //------------------------------------------------------------

  void visitTensorDim(tensor::DimOp dim) {

    Value tensor = dim.getSource();

    if (!runtimeTainted.count(tensor))
      return;

    Value result = dim.getResult();

    stagingTainted.insert(result);

    llvm::errs()
        << "\n[Runtime -> Staging]\n";

    llvm::errs()
        << "tensor : ";

    tensor.print(llvm::errs());

    llvm::errs()
        << "\nindex  : ";

    result.print(llvm::errs());

    llvm::errs()
        << "\n";
  }

 void visitOperation(Operation *op) {

    if (auto dim = dyn_cast<tensor::DimOp>(op)) {
        visitTensorDim(dim);
        return;
    }

    visitGenericRuntimePropagation(op);

    visitArithmeticStagingPropagation(op);

    if (auto loop = dyn_cast<affine::AffineForOp>(op))
        visitAffineFor(loop);

    if (auto loop = dyn_cast<scf::ForOp>(op))
        visitScfFor(loop);

    if (auto load = dyn_cast<affine::AffineLoadOp>(op))
        visitAffineLoad(load);

    if (auto store = dyn_cast<affine::AffineStoreOp>(op))
        visitAffineStore(store);
}

//------------------------------------------------------------
// affine.load
//------------------------------------------------------------

void visitAffineLoad(affine::AffineLoadOp load) {

    for (Value index : load.getIndices()) {

        if (!isStagingTainted(index))
            continue;

        reportViolation(
            load,
            index,
            "affine.load address depends on protected runtime data");
    }
}

//------------------------------------------------------------
// affine.store
//------------------------------------------------------------

void visitAffineStore(affine::AffineStoreOp store) {

    for (Value index : store.getIndices()) {

        if (!isStagingTainted(index))
            continue;

        reportViolation(
            store,
            index,
            "affine.store address depends on protected runtime data");
    }
}

//------------------------------------------------------------
// Generic runtime propagation
//------------------------------------------------------------

void visitGenericRuntimePropagation(Operation *op) {

    bool runtime = false;

    //--------------------------------------------------------
    // Is any operand runtime tainted?
    //--------------------------------------------------------

    for (Value operand : op->getOperands()) {

        if (runtimeTainted.count(operand)) {
            runtime = true;
            break;
        }
    }

    if (!runtime)
        return;

    //--------------------------------------------------------
    // Mark every result runtime tainted
    //--------------------------------------------------------

    for (Value result : op->getResults()) {

        if (runtimeTainted.insert(result).second) {

            llvm::errs()
                << "\n[Runtime Propagation]\n";

            llvm::errs()
                << "Operation : "
                << op->getName().getStringRef()
                << "\n";

            llvm::errs()
                << "Result : ";

            result.print(llvm::errs());

            llvm::errs()
                << "\n";
        }
    }
}

//------------------------------------------------------------
// Generic staging propagation
//------------------------------------------------------------

void visitArithmeticStagingPropagation(Operation *op) {

  //--------------------------------------------------------
  // Only propagate through supported arithmetic operations
  //--------------------------------------------------------

  if (!isa<
          arith::AddIOp,
          arith::SubIOp,
          arith::MulIOp,
          arith::DivSIOp,
          arith::DivUIOp,
          arith::RemSIOp,
          arith::RemUIOp,
          arith::IndexCastOp,
          arith::MaxSIOp,
          arith::MinSIOp>(op))
    return;

  //--------------------------------------------------------
  // Does any operand carry staging taint?
  //--------------------------------------------------------

  bool hasStagingInput = false;

  for (Value operand : op->getOperands()) {
    if (stagingTainted.count(operand)) {
      hasStagingInput = true;
      break;
    }
  }

  if (!hasStagingInput)
    return;

  //--------------------------------------------------------
  // Propagate to index results
  //--------------------------------------------------------

  for (Value result : op->getResults()) {

    if (!result.getType().isIndex())
      continue;

    if (stagingTainted.insert(result).second) {

      llvm::errs() << "\n[Staging Propagation]\n";
      llvm::errs() << "Operation : "
                   << op->getName().getStringRef() << "\n";

      llvm::errs() << "Result : ";
      result.print(llvm::errs());
      llvm::errs() << "\n";
    }
  }
}
  //------------------------------------------------------------
// Is this value staging tainted?
//------------------------------------------------------------

bool isStagingTainted(Value value) const {

  return stagingTainted.count(value);
}

//------------------------------------------------------------
// Report violation
//------------------------------------------------------------

void reportViolation(Operation *op,
                     Value offendingValue,
                     StringRef reason) {

  op->emitError()
      << "Staging Non-Interference violation: "
      << reason;

  llvm::errs() << "\n========== VIOLATION ==========\n";

  llvm::errs()
      << reason
      << "\n";

  llvm::errs()
      << "Offending value: ";

  offendingValue.print(llvm::errs());

  llvm::errs() << "\n";
}

//------------------------------------------------------------
// affine.for
//------------------------------------------------------------

void visitAffineFor(affine::AffineForOp loop) {

  for (Value v : loop.getLowerBoundOperands()) {

    if (isStagingTainted(v))
      reportViolation(
          loop,
          v,
          "loop lower bound depends on protected runtime data");
  }

  for (Value v : loop.getUpperBoundOperands()) {

    if (isStagingTainted(v))
      reportViolation(
          loop,
          v,
          "loop upper bound depends on protected runtime data");
  }
}

//------------------------------------------------------------
// scf.for
//------------------------------------------------------------

void visitScfFor(scf::ForOp loop) {

  if (isStagingTainted(loop.getLowerBound()))
    reportViolation(
        loop,
        loop.getLowerBound(),
        "loop lower bound depends on protected runtime data");

  if (isStagingTainted(loop.getUpperBound()))
    reportViolation(
        loop,
        loop.getUpperBound(),
        "loop upper bound depends on protected runtime data");

  if (isStagingTainted(loop.getStep()))
    reportViolation(
        loop,
        loop.getStep(),
        "loop step depends on protected runtime data");
}

  //------------------------------------------------------------
  // Summary
  //------------------------------------------------------------

  void printSummary() {

    llvm::errs()
        << "\n==============================\n";

    llvm::errs()
        << "Runtime tainted values : "
        << runtimeTainted.size()
        << "\n";

    llvm::errs()
        << "Staging tainted values : "
        << stagingTainted.size()
        << "\n";

    llvm::errs()
        << "==============================\n";
  }
};

  std::unique_ptr<Pass>
createVerifyStagingNonInterferencePass() {
    return std::make_unique<VerifyStagingNonInterferencePass>();
}

void registerPasses() {
    PassRegistration<VerifyStagingNonInterferencePass>();
}
}}