// Spike: over-approximate Low/High taint scan over LLVM-dialect MLIR.
// Built out-of-tree against Homebrew LLVM/MLIR 17.0.6.
#include "mlir/Analysis/DataFlow/DeadCodeAnalysis.h"
#include "mlir/Analysis/DataFlow/SparseAnalysis.h"
#include "mlir/Analysis/DataFlowFramework.h"
#include "mlir/Dialect/DLTI/DLTI.h"
#include "mlir/Dialect/LLVMIR/LLVMDialect.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/MLIRContext.h"
#include "mlir/Parser/Parser.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/InitLLVM.h"
#include "llvm/Support/raw_ostream.h"

using namespace mlir;
using namespace mlir::dataflow;

namespace {

// ---- Lattice value: Low ⊑ High -------------------------------------------
struct Secrecy {
  bool high = false;
  static Secrecy join(const Secrecy &a, const Secrecy &b) {
    return Secrecy{a.high || b.high};
  }
  bool operator==(const Secrecy &o) const { return high == o.high; }
  void print(raw_ostream &os) const { os << (high ? "high" : "low"); }
};

using SecrecyLattice = Lattice<Secrecy>;

// ---- Forward sparse analysis ---------------------------------------------
class SecrecyAnalysis : public SparseDataFlowAnalysis<SecrecyLattice> {
public:
  using SparseDataFlowAnalysis::SparseDataFlowAnalysis;

  void visitOperation(Operation *op, ArrayRef<const SecrecyLattice *> operands,
                      ArrayRef<SecrecyLattice *> results) override {
    Secrecy acc;
    for (const SecrecyLattice *in : operands)
      acc = Secrecy::join(acc, in->getValue());
    // Explicit op-level override, if the fixture declares one.
    if (auto attr = op->getAttrOfType<StringAttr>("sps.label"))
      if (attr.getValue() == "high")
        acc.high = true;
    for (SecrecyLattice *out : results)
      propagateIfChanged(out, out->join(acc));
  }

  // The framework routes BOTH "declared program entry" and "we lost track"
  // through this single hook. We disambiguate on the Value itself.
  void setToEntryState(SecrecyLattice *lattice) override {
    Value v = lattice->getPoint();
    if (auto arg = dyn_cast<BlockArgument>(v)) {
      Block *b = arg.getOwner();
      if (b->isEntryBlock())
        if (auto fn = dyn_cast<LLVM::LLVMFuncOp>(b->getParentOp())) {
          auto lbl = fn.getArgAttrOfType<StringAttr>(arg.getArgNumber(),
                                                     "sps.label");
          bool high = lbl && lbl.getValue() == "high";
          // Declared "low" stays low; undeclared defaults conservatively high.
          if (!lbl)
            high = defaultArgHigh;
          propagateIfChanged(lattice, lattice->join(Secrecy{high}));
          return;
        }
    }
    // Genuine loss of information (unresolved call, non-branch predecessor):
    // must be High to stay over-approximate.
    propagateIfChanged(lattice, lattice->join(Secrecy{true}));
  }

  bool defaultArgHigh = false;
};

// Refinement: a High *pointer* only leaks an address if the secrecy actually
// entered through a computed offset. A pointer that is High only because it is
// an undeclared argument carries no secret-dependent displacement.
bool addressIsSecretDisplaced(DataFlowSolver &solver, Value addr);

bool isHigh(DataFlowSolver &solver, Value v) {
  const auto *l = solver.lookupState<SecrecyLattice>(v);
  return !l || l->getValue().high; // missing state == never reached == be loud
}

bool addressIsSecretDisplaced(DataFlowSolver &solver, Value addr) {
  Operation *def = addr.getDefiningOp();
  if (!def)
    return false; // bare block argument: no computed displacement
  if (auto gep = dyn_cast<LLVM::GEPOp>(def)) {
    for (Value idx : gep.getDynamicIndices())
      if (isHigh(solver, idx))
        return true;
    return addressIsSecretDisplaced(solver, gep.getBase());
  }
  if (isa<LLVM::AllocaOp>(def))
    return false;
  return isHigh(solver, addr); // ptrtoint/select/phi arithmetic: stay loud
}

} // namespace

static llvm::cl::opt<std::string> inputFile(llvm::cl::Positional,
                                            llvm::cl::Required);
static llvm::cl::opt<bool>
    defaultHigh("default-arg-high",
                llvm::cl::desc("treat undeclared function args as secret"),
                llvm::cl::init(false));
static llvm::cl::opt<bool>
    refineAddr("refine-address",
               llvm::cl::desc("only flag addresses with secret displacement"),
               llvm::cl::init(false));

int main(int argc, char **argv) {
  llvm::InitLLVM x(argc, argv);
  llvm::cl::ParseCommandLineOptions(argc, argv, "sps-scan spike\n");

  MLIRContext ctx;
  ctx.getOrLoadDialect<LLVM::LLVMDialect>();
  ctx.getOrLoadDialect<DLTIDialect>();
  auto mod = parseSourceFile<ModuleOp>(inputFile, &ctx);
  if (!mod) {
    llvm::errs() << "parse failed\n";
    return 1;
  }

  DataFlowSolver solver;
  solver.load<DeadCodeAnalysis>();
  solver.load<SecrecyAnalysis>()->defaultArgHigh = defaultHigh;
  if (failed(solver.initializeAndRun(*mod))) {
    llvm::errs() << "solver failed\n";
    return 1;
  }

  unsigned findings = 0;
  auto report = [&](Operation *op, StringRef reason) {
    ++findings;
    llvm::outs() << "  [" << reason << "] " << op->getName() << " @ "
                 << op->getLoc() << "\n";
  };

  // Sinks are ops with NO results, so the sparse analysis never visits them.
  // Checking therefore has to be a separate post-solve walk.
  mod->walk([&](Operation *op) {
    if (auto br = dyn_cast<LLVM::CondBrOp>(op)) {
      if (isHigh(solver, br.getCondition()))
        report(op, "secret-dependent-branch");
    } else if (auto sw = dyn_cast<LLVM::SwitchOp>(op)) {
      if (isHigh(solver, sw.getValue()))
        report(op, "secret-dependent-branch");
    } else if (auto st = dyn_cast<LLVM::StoreOp>(op)) {
      auto sink = op->getAttrOfType<StringAttr>("sps.sink_class");
      bool publicSink = sink && sink.getValue() == "public";
      if (publicSink && isHigh(solver, st.getValue()))
        report(op, "secret-to-public-sink");
      if (refineAddr ? addressIsSecretDisplaced(solver, st.getAddr())
                     : isHigh(solver, st.getAddr()))
        report(op, "secret-dependent-address");
    } else if (auto ld = dyn_cast<LLVM::LoadOp>(op)) {
      if (refineAddr ? addressIsSecretDisplaced(solver, ld.getAddr())
                     : isHigh(solver, ld.getAddr()))
        report(op, "secret-dependent-address");
    } else if (isa<LLVM::UDivOp, LLVM::SDivOp, LLVM::URemOp, LLVM::SRemOp>(
                   op)) {
      if (isHigh(solver, op->getOperand(0)) || isHigh(solver, op->getOperand(1)))
        report(op, "secret-dependent-variable-latency-op");
    } else if (auto al = dyn_cast<LLVM::AllocaOp>(op)) {
      if (isHigh(solver, al.getArraySize()))
        report(op, "secret-dependent-allocation-size");
    }
  });
  llvm::outs() << "findings: " << findings << "\n";
  return 0;
}
