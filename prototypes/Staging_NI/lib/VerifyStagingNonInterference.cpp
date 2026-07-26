#include "stagingNI/Passes.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/Operation.h"
#include "mlir/IR/Value.h"
#include "mlir/Pass/Pass.h"
#include "llvm/Support/raw_ostream.h"
#include "mlir/Dialect/Tensor/IR/Tensor.h"
#include "llvm/ADT/DenseSet.h"
#include "llvm/ADT/STLExtras.h"
#include "mlir/Dialect/Affine/IR/AffineOps.h"
#include "mlir/Dialect/SCF/IR/SCF.h"

using namespace mlir;

namespace mlir {
namespace stagingni {

#define GEN_PASS_DEF_VERIFYSTAGINGNONINTERFERENCE
#include "stagingNI/Passes.h.inc"

namespace {
class VerifyStagingNonInterferencePass
    : public impl::VerifyStagingNonInterferenceBase<
          VerifyStagingNonInterferencePass> {

public:
  using VerifyStagingNonInterferenceBase::VerifyStagingNonInterferenceBase;

  void runOnOperation() override {

    func::FuncOp func = getOperation();

    runtimeTainted.clear();
    stagingTainted.clear();
    sawViolation = false;
    sawUnknown = false;

    seedRuntimeTaint(func);

    // Pre-order: a loop's bound/iter_args are seeded onto its induction
    // var/region args by visiting the loop OP itself (visitAffineFor/
    // visitScfFor), and that seeded taint must be visible to uses INSIDE
    // the loop body. walk()'s default is post-order (children before
    // parent) -- under that order every such nested use is checked before
    // the parent loop op seeds it, silently missing it. Pre-order visits
    // the loop op first, then its body, which is the order this analysis
    // actually depends on.
    func.walk<WalkOrder::PreOrder>([&](Operation *op) {
      visitOperation(op);
    });

    printSummary();

    // Violations are collected across the whole function before we decide
    // pass/fail (see reportViolation) -- one bad site should not hide the
    // rest. UNKNOWN sites are surfaced (emitRemark, see reportUnknown) but do
    // not fail the pass: they mean "not modeled", not "confirmed bad", and
    // this analysis is known-incomplete by design (see readme's Current
    // Limitations) -- failing the build on every unmodeled construct would
    // make the checker useless long before it's complete. A confirmed
    // VIOLATION does fail it, so a real pipeline can gate on this pass.
    if (sawViolation)
      signalPassFailure();
  }

private:

  //------------------------------------------------------------
  // Two taint domains
  //------------------------------------------------------------

  llvm::DenseSet<Value> runtimeTainted;
  llvm::DenseSet<Value> stagingTainted;
  bool sawViolation = false;
  bool sawUnknown = false;

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

  //------------------------------------------------------------
  // arith.index_cast of RUNTIME-tainted data: a second Runtime -> Staging
  // conversion point alongside tensor.dim.
  //------------------------------------------------------------

  // Casting protected data to `index` is precisely how it becomes eligible
  // to drive a loop bound or address -- tensor.dim is one such cast
  // (tensor rank/extent -> index); a scalar loaded from a protected
  // memref/buffer and cast to index is another (e.g. mlir_leak's
  // `dynshape.mlir`: a secret extent `k` loaded from a memref, then
  // `arith.index_cast`'d and used as a `memref.alloc`/`scf.for` bound).
  // Without this, runtime taint propagated generically through the load
  // and the cast (visitGenericRuntimePropagation marks the cast's result
  // runtime-tainted), but nothing ever promoted it to STAGING taint, so
  // every bound/address check below silently saw an untainted value --
  // this analysis could not catch the one case mlir_leak already measured
  // and confirmed leaks on every lowering pipeline and every -O level.
  void visitRuntimeToStagingCast(arith::IndexCastOp cast) {

    Value in = cast.getIn();

    if (!runtimeTainted.count(in))
      return;

    Value result = cast.getResult();

    if (!stagingTainted.insert(result).second)
      return;

    llvm::errs()
        << "\n[Runtime -> Staging via index_cast]\n";
    llvm::errs() << "source : ";
    in.print(llvm::errs());
    llvm::errs() << "\nindex  : ";
    result.print(llvm::errs());
    llvm::errs() << "\n";
  }

 void visitOperation(Operation *op) {

    if (auto dim = dyn_cast<tensor::DimOp>(op)) {
        visitTensorDim(dim);
        return;
    }

    // secret.generic is not in this project's dialect registry (linking
    // HEIR's Secret dialect would pull in a second, Bazel-built subproject),
    // so it can't be dyn_cast'd here. Matched by name instead: its region
    // body could re-taint, launder, or leak a tainted operand in ways this
    // walker does not model, so it must be surfaced as UNKNOWN rather than
    // silently treated as a taint barrier.
    if (op->getName().getStringRef() == "secret.generic") {
        visitSecretGeneric(op);
        return;
    }

    visitGenericRuntimePropagation(op);

    visitArithmeticStagingPropagation(op);

    if (auto cast = dyn_cast<arith::IndexCastOp>(op))
        visitRuntimeToStagingCast(cast);

    if (auto loop = dyn_cast<affine::AffineForOp>(op))
        visitAffineFor(loop);

    if (auto loop = dyn_cast<scf::ForOp>(op))
        visitScfFor(loop);

    if (auto load = dyn_cast<affine::AffineLoadOp>(op))
        visitAffineLoad(load);

    if (auto store = dyn_cast<affine::AffineStoreOp>(op))
        visitAffineStore(store);

    if (auto ifOp = dyn_cast<scf::IfOp>(op))
        visitScfIf(ifOp);

    if (auto whileOp = dyn_cast<scf::WhileOp>(op))
        visitScfWhile(whileOp);

    if (auto cond = dyn_cast<scf::ConditionOp>(op))
        visitScfCondition(cond);
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

  // arith.cmpi is included so a staging-tainted index can reach an i1 used
  // as an scf.if/scf.while condition: without it, visitScfIf/
  // visitScfCondition can only ever fire on a condition that is ALREADY i1
  // and ALREADY tainted, which nothing upstream can ever produce (every
  // realistic condition is built from a comparison over index-typed data).
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
          arith::MinSIOp,
          arith::CmpIOp>(op))
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
  // Propagate to index results (loop bounds/addresses) and i1 results
  // (arith.cmpi, feeding an scf.if/scf.while condition)
  //--------------------------------------------------------

  for (Value result : op->getResults()) {

    if (!result.getType().isIndex() && !result.getType().isInteger(1))
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
// Taint queries
//------------------------------------------------------------

bool isStagingTainted(Value value) const {

  return stagingTainted.count(value);
}

bool isRuntimeTainted(Value value) const {

  return runtimeTainted.count(value);
}

bool isTainted(Value value) const {

  return isStagingTainted(value) || isRuntimeTainted(value);
}

//------------------------------------------------------------
// Report violation / unknown
//------------------------------------------------------------

void reportViolation(Operation *op,
                     Value offendingValue,
                     StringRef reason) {

  sawViolation = true;

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

// UNKNOWN means "this analysis cannot model what happens here", which is
// weaker than SAFE, not stronger: the earlier design silently treated every
// unmodeled construct as a taint barrier (safe by omission). That is
// unsound -- it is the same mistake as reading a formal tool's "unknown" as
// "secure" instead of "silent" (see the project's own formal_verif/infoleak
// FTZ layer, which exists specifically because binsec is silent -- not
// secure -- on FP kernels). A remark, not an error: "cannot verify" should
// be visible, not fatal, or the checker becomes useless before it's complete.
void reportUnknown(Operation *op, StringRef reason) {

  sawUnknown = true;

  op->emitRemark()
      << "Staging Non-Interference: UNKNOWN - " << reason
      << " (unmodeled construct; not provably safe)";

  llvm::errs() << "\n========== UNKNOWN ==========\n";

  llvm::errs()
      << reason
      << "\n";
}

//------------------------------------------------------------
// affine.for
//------------------------------------------------------------

void visitAffineFor(affine::AffineForOp loop) {

  bool boundTainted = false;

  for (Value v : loop.getLowerBoundOperands()) {

    if (isStagingTainted(v)) {
      reportViolation(
          loop,
          v,
          "loop lower bound depends on protected runtime data");
      boundTainted = true;
    }
  }

  for (Value v : loop.getUpperBoundOperands()) {

    if (isStagingTainted(v)) {
      reportViolation(
          loop,
          v,
          "loop upper bound depends on protected runtime data");
      boundTainted = true;
    }
  }

  // The induction variable (and any iter_args) range over a tainted bound,
  // so any downstream use of it -- e.g. as an affine.load/store index -- is
  // staging-tainted too. Not seeding this was a silent false negative: only
  // the loop op itself was ever flagged, never derived uses of the
  // induction variable in the body (readme's "block argument propagation"
  // gap, for the one case -- loop induction vars -- this walker can resolve
  // outright instead of reporting UNKNOWN).
  if (boundTainted) {
    for (Value iv : loop.getBody()->getArguments())
      stagingTainted.insert(iv);
  }
}

//------------------------------------------------------------
// scf.for
//------------------------------------------------------------

void visitScfFor(scf::ForOp loop) {

  bool boundTainted = false;

  if (isStagingTainted(loop.getLowerBound())) {
    reportViolation(
        loop,
        loop.getLowerBound(),
        "loop lower bound depends on protected runtime data");
    boundTainted = true;
  }

  if (isStagingTainted(loop.getUpperBound())) {
    reportViolation(
        loop,
        loop.getUpperBound(),
        "loop upper bound depends on protected runtime data");
    boundTainted = true;
  }

  if (isStagingTainted(loop.getStep())) {
    reportViolation(
        loop,
        loop.getStep(),
        "loop step depends on protected runtime data");
    boundTainted = true;
  }

  if (boundTainted)
    stagingTainted.insert(loop.getInductionVar());

  // iter_args: a tainted init value flows into the corresponding region
  // block argument on every iteration (and back in via scf.yield). Not
  // propagating this was a silent false negative -- readme's explicitly
  // documented "scf.for iter_args propagation" gap -- and it is a real,
  // resolvable dataflow edge, not an unmodeled one.
  for (auto [init, arg] :
       llvm::zip(loop.getInitArgs(), loop.getRegionIterArgs())) {
    if (isRuntimeTainted(init))
      runtimeTainted.insert(arg);
    if (isStagingTainted(init))
      stagingTainted.insert(arg);
  }
}

//------------------------------------------------------------
// scf.if / scf.while: staging-time control flow
//------------------------------------------------------------

void visitScfIf(scf::IfOp ifOp) {

  if (isStagingTainted(ifOp.getCondition()))
    reportViolation(
        ifOp,
        ifOp.getCondition(),
        "branch condition depends on protected runtime data "
        "(staging-time control flow)");
}

void visitScfCondition(scf::ConditionOp cond) {

  if (isStagingTainted(cond.getCondition()))
    reportViolation(
        cond,
        cond.getCondition(),
        "scf.while condition depends on protected runtime data "
        "(staging-time control flow)");
}

// scf.while's "before" region computes the condition (via scf.condition,
// above) from its own block arguments, which are seeded from the init
// operands on entry -- the same init-value -> region-block-arg edge as
// scf.for's iter_args, so it gets the same fix: propagate taint across it
// instead of silently dropping it at the region boundary.
void visitScfWhile(scf::WhileOp whileOp) {

  Block &before = whileOp.getBefore().front();

  for (auto [init, arg] :
       llvm::zip(whileOp.getInits(), before.getArguments())) {
    if (isRuntimeTainted(init))
      runtimeTainted.insert(arg);
    if (isStagingTainted(init))
      stagingTainted.insert(arg);
  }
}

//------------------------------------------------------------
// secret.generic: unmodeled region -- UNKNOWN, not silently safe
//------------------------------------------------------------

void visitSecretGeneric(Operation *op) {

  bool anyTainted = false;

  for (Value operand : op->getOperands()) {
    if (isTainted(operand)) {
      anyTainted = true;
      break;
    }
  }

  if (!anyTainted)
    return;

  reportUnknown(
      op,
      "secret.generic region body is not modeled by this analysis; a "
      "tainted operand may be relaundered or re-leaked inside it");
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
        << "Violations reported    : "
        << (sawViolation ? "yes" : "no")
        << "\n";

    llvm::errs()
        << "Unknown (unmodeled)    : "
        << (sawUnknown ? "yes" : "no")
        << "\n";

    llvm::errs()
        << "==============================\n";
  }
};
} // namespace
}}
