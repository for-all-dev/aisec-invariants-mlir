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
#include "mlir/Dialect/ControlFlow/IR/ControlFlowOps.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/Dialect/SCF/IR/SCF.h"
#include "mlir/Interfaces/ControlFlowInterfaces.h"

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

    // Propagate to a FIXPOINT before reporting anything.
    //
    // A single pass is order-dependent, and no single order is correct:
    // taint flows forward along SSA (parent op before its region), but also
    // BACKWARD around a loop's back edge (scf.yield re-binds the iter_args
    // for the next iteration) and outward from a region terminator onto the
    // parent op's results. A one-shot walk therefore missed anything whose
    // taint became known only after the point it was needed -- e.g.
    // mlir_leak's cond_reduce, where the secret is reduced inside an
    // scf.for and only the loop's RESULT feeds the branch: measured
    // leaking, reported oblivious here.
    //
    // Iterating until the taint sets stop growing removes the ordering
    // question entirely. The sets only ever grow and are bounded by the
    // number of SSA values, so this terminates.
    //
    // Pre-order is kept because it converges in fewer rounds (a loop op
    // seeds its induction var before its body is walked), not because
    // correctness depends on it any more.
    reporting = false;
    for (unsigned round = 0;; ++round) {
      size_t before = runtimeTainted.size() + stagingTainted.size();
      func.walk<WalkOrder::PreOrder>([&](Operation *op) { visitOperation(op); });
      if (runtimeTainted.size() + stagingTainted.size() == before)
        break;
      if (round > kMaxRounds) {
        func.emitWarning()
            << "staging-ni: taint propagation did not converge in "
            << kMaxRounds << " rounds; results may be incomplete";
        break;
      }
    }

    // One final walk, now that the taint sets are stable, to emit
    // diagnostics exactly once each.
    reporting = true;
    func.walk<WalkOrder::PreOrder>([&](Operation *op) { visitOperation(op); });

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
  // Diagnostics are emitted only on the final walk, after the taint sets
  // have converged; the propagation rounds before it would otherwise report
  // the same site once per round.
  bool reporting = true;
  static constexpr unsigned kMaxRounds = 64;

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

    visitGenericStagingPropagation(op);

    if (auto cast = dyn_cast<arith::IndexCastOp>(op))
        visitRuntimeToStagingCast(cast);

    // Memory writes: taint the destination buffer (see visitStore).
    if (auto st = dyn_cast<memref::StoreOp>(op))
        visitStore(op, st.getValueToStore(), st.getMemRef());

    if (auto st = dyn_cast<affine::AffineStoreOp>(op))
        visitStore(op, st.getValueToStore(), st.getMemRef());

    // Constructs whose taint behaviour this analysis does not model.
    visitUnmodeledAliasing(op);
    visitCall(op);

    if (op->hasTrait<OpTrait::IsTerminator>())
        visitRegionTerminator(op);

    visitBranchOperands(op);

    if (auto loop = dyn_cast<affine::AffineForOp>(op))
        visitAffineFor(loop);

    if (auto loop = dyn_cast<scf::ForOp>(op))
        visitScfFor(loop);

    if (auto load = dyn_cast<affine::AffineLoadOp>(op))
        visitAffineLoad(load);

    if (auto store = dyn_cast<affine::AffineStoreOp>(op))
        visitAffineStore(store);

    // memref.load/store, not just their affine counterparts. Address sinks
    // that only covered the affine forms missed the plain-memref one
    // entirely -- mlir_leak's idx_gather (`table[secret_idx]`, its canonical
    // ADDRESS-channel kernel, measured leaking at every -O level) is written
    // with memref.load and was reported oblivious.
    if (auto load = dyn_cast<memref::LoadOp>(op))
        visitAddressIndices(op, load.getIndices(), "memref.load");

    if (auto store = dyn_cast<memref::StoreOp>(op))
        visitAddressIndices(op, store.getIndices(), "memref.store");

    if (auto ifOp = dyn_cast<scf::IfOp>(op))
        visitScfIf(ifOp);

    if (auto whileOp = dyn_cast<scf::WhileOp>(op))
        visitScfWhile(whileOp);

    if (auto cond = dyn_cast<scf::ConditionOp>(op))
        visitScfCondition(cond);

    // cf.cond_br is what scf.if/scf.for BECOME after --convert-scf-to-cf.
    // Checking only the scf forms meant the analysis went blind on exactly
    // the same program one standard lowering step later -- and silently, so
    // a before/after comparison would have read that blindness as the leak
    // having been removed.
    if (auto br = dyn_cast<cf::CondBranchOp>(op))
        visitCondBranch(br);
}

//------------------------------------------------------------
// affine.load
//------------------------------------------------------------

void visitAffineLoad(affine::AffineLoadOp load) {

    for (Value index : load.getIndices()) {

        if (!isTainted(index))
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

        if (!isTainted(index))
            continue;

        reportViolation(
            store,
            index,
            "affine.store address depends on protected runtime data");
    }
}

//------------------------------------------------------------
// Region terminators: carry taint OUT of a region
//------------------------------------------------------------

// A value computed inside a region and yielded from it becomes (a) the
// parent op's corresponding RESULT and (b), around a loop's back edge, the
// corresponding iter_arg on the next iteration. Neither edge existed, so
// taint entered a region and never came back out: mlir_leak's cond_reduce
// reduces the secret inside an scf.for and branches on the loop's result,
// which this analysis called oblivious while the measurement called it a
// leak.
//
// Terminator-agnostic (any op with IsTerminator, matched positionally),
// so scf.yield/affine.yield/scf.condition and any other dialect's region
// terminator all work without enumerating them -- an enumeration here would
// be the same silent-safe whitelist that was removed from the propagation
// rule.
void carryTaint(Value from, Value to) {
  if (isRuntimeTainted(from))
    runtimeTainted.insert(to);
  if (isStagingTainted(from))
    stagingTainted.insert(to);
}

// Branch successor operands -> successor BLOCK ARGUMENTS.
//
// This is the cf-dialect twin of the region-terminator edge below, and it
// is what keeps the analysis alive after --convert-scf-to-cf: that pass
// turns loop-carried values and scf.if results into block arguments passed
// by cf.br/cf.cond_br. Without this edge taint died at every block
// boundary, so a lowered program looked clean -- and a before/after
// comparison read that blindness as `lowering-removed`. Caught by
// cross-checking against mlir_leak's cond_reduce, which is measured leaking
// on every pipeline but was reported "removed" here.
//
// Via BranchOpInterface rather than naming cf ops, so any dialect's
// branch-like op participates.
void visitBranchOperands(Operation *op) {

  auto branch = dyn_cast<BranchOpInterface>(op);
  if (!branch)
    return;

  for (unsigned s = 0, e = op->getNumSuccessors(); s < e; ++s) {
    SuccessorOperands succOps = branch.getSuccessorOperands(s);
    Block *dest = op->getSuccessor(s);
    for (unsigned i = succOps.getProducedOperandCount(), n = succOps.size();
         i < n; ++i) {
      if (i >= dest->getNumArguments())
        break;
      if (Value from = succOps[i])
        carryTaint(from, dest->getArgument(i));
    }
  }
}

void visitRegionTerminator(Operation *term) {

  Operation *parent = term->getParentOp();
  if (!parent)
    return;

  auto carry = [&](Value from, Value to) { carryTaint(from, to); };

  // yielded value i -> parent result i
  for (auto [operand, result] :
       llvm::zip(term->getOperands(), parent->getResults()))
    carry(operand, result);

  // yielded value i -> the region argument it re-binds (loop back edge).
  // Offset because a loop body's first argument is the induction variable,
  // which is not carried; zip over the TAIL that matches the yield's arity.
  Region *region = term->getParentRegion();
  if (!region || region->empty())
    return;
  Block &entry = region->front();
  unsigned nYield = term->getNumOperands();
  unsigned nArgs = entry.getNumArguments();
  if (nYield && nArgs >= nYield)
    for (unsigned i = 0; i < nYield; ++i)
      carry(term->getOperand(i), entry.getArgument(nArgs - nYield + i));
}

//------------------------------------------------------------
// Address indices (shared by the affine and memref forms)
//------------------------------------------------------------

void visitAddressIndices(Operation *op, ValueRange indices, StringRef what) {

  for (Value index : indices) {

    if (!isTainted(index))
      continue;

    reportViolation(
        op, index,
        (what + " address depends on protected runtime data").str());
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

// Propagates through ANY operation, exactly like runtime taint above.
//
// This used to be gated on a whitelist of arith ops (addi/subi/muli/divs/
// divu/rems/remu/index_cast/maxsi/minsi/cmpi). A whitelist is a silent-safe
// construct by design: an operation NOT on it that consumed a
// staging-tainted value produced an untainted result, so the taint vanished
// with no diagnostic -- arith.shli, affine.apply, arith.select, index.add,
// any dialect the whitelist had not enumerated. Every op added to MLIR was
// a new hole, and the analysis reported "no violation" for all of them.
//
// Over-approximating instead is the direction this project already takes
// elsewhere (prototypes/initial's VerifyNonInterference: "if ANY operand of
// an op is tainted, ALL of its results become tainted -- imprecise but
// sound"). Results of any type are marked: the sinks below only ever
// consult index/i1 operands, so tainting e.g. an f32 costs nothing in
// precision there, while dropping it would reopen the hole for a value that
// is later cast back to index.
void visitGenericStagingPropagation(Operation *op) {

  bool hasStagingInput = false;

  for (Value operand : op->getOperands()) {
    if (stagingTainted.count(operand)) {
      hasStagingInput = true;
      break;
    }
  }

  if (!hasStagingInput)
    return;

  for (Value result : op->getResults()) {

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
// Memory: a store of tainted data taints the destination buffer
//------------------------------------------------------------

// Without this the analysis loses taint completely across a memory
// round-trip -- `memref.store %secret, %slot[...]` then `memref.load
// %slot[...]` produced a clean value, and the leak downstream of it was
// reported as no violation AND no UNKNOWN. Verified silent before this
// change; test/memory-roundtrip.mlir pins it.
//
// A store has no results, so generic propagation cannot see it: the buffer
// is an OPERAND. Taint the buffer value itself, and generic propagation
// then carries it to any load's result (the load's memref operand is
// tainted).
//
// Deliberately coarse -- whole-buffer, no indices, no alias analysis. A
// tainted store anywhere in a memref makes every later load from that SSA
// value tainted, including loads of untouched slots. That over-approximates
// (false positives) rather than under-approximating (silent misses), which
// is the only acceptable direction here. True aliasing (two SSA values for
// one allocation, via memref.cast/subview/function arguments) is NOT
// modeled and is reported as UNKNOWN by visitUnmodeledAliasing below.
void visitStore(Operation *op, Value stored, Value dest) {

  if (!isTainted(stored))
    return;

  bool newRuntime = isRuntimeTainted(stored) && runtimeTainted.insert(dest).second;
  bool newStaging = isStagingTainted(stored) && stagingTainted.insert(dest).second;

  if (!newRuntime && !newStaging)
    return;

  llvm::errs() << "\n[Taint -> Memory]\n";
  llvm::errs() << "Operation : " << op->getName().getStringRef() << "\n";
  llvm::errs() << "Buffer : ";
  dest.print(llvm::errs());
  llvm::errs() << "\n";
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

  if (!reporting)
    return;

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

  if (!reporting)
    return;

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

    if (isTainted(v)) {
      reportViolation(
          loop,
          v,
          "loop lower bound depends on protected runtime data");
      boundTainted = true;
    }
  }

  for (Value v : loop.getUpperBoundOperands()) {

    if (isTainted(v)) {
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

  if (isTainted(loop.getLowerBound())) {
    reportViolation(
        loop,
        loop.getLowerBound(),
        "loop lower bound depends on protected runtime data");
    boundTainted = true;
  }

  if (isTainted(loop.getUpperBound())) {
    reportViolation(
        loop,
        loop.getUpperBound(),
        "loop upper bound depends on protected runtime data");
    boundTainted = true;
  }

  if (isTainted(loop.getStep())) {
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

  if (isTainted(ifOp.getCondition()))
    reportViolation(
        ifOp,
        ifOp.getCondition(),
        "branch condition depends on protected runtime data "
        "(staging-time control flow)");
}

void visitScfCondition(scf::ConditionOp cond) {

  if (isTainted(cond.getCondition()))
    reportViolation(
        cond,
        cond.getCondition(),
        "scf.while condition depends on protected runtime data "
        "(staging-time control flow)");
}

// cf.cond_br: the lowered form of every staging-time branch. Same finding
// as visitScfIf, one dialect down.
void visitCondBranch(cf::CondBranchOp br) {

  if (isTainted(br.getCondition()))
    reportViolation(
        br,
        br.getCondition(),
        "branch condition depends on protected runtime data "
        "(staging-time control flow)");
}

//------------------------------------------------------------
// Unmodeled: aliasing and interprocedural flow -> UNKNOWN
//------------------------------------------------------------

// The memory model above is per-SSA-value: it taints the buffer VALUE a
// store targets. Any op that produces a second SSA handle onto the same
// underlying allocation (cast/subview/view/reinterpret_cast/collapse/expand)
// therefore breaks it -- a store through one handle is invisible to a load
// through the other. Generic propagation covers the case where the tainted
// handle is the one being re-derived; what it cannot cover is the reverse
// order (derive handle B from clean A, store through A, load through B).
// Rather than pretend either way, report UNKNOWN whenever a tainted memref
// is re-handled at all.
void visitUnmodeledAliasing(Operation *op) {

  if (!isa<memref::CastOp, memref::SubViewOp, memref::ViewOp,
           memref::ReinterpretCastOp, memref::CollapseShapeOp,
           memref::ExpandShapeOp>(op))
    return;

  for (Value operand : op->getOperands()) {
    if (!isTainted(operand))
      continue;
    reportUnknown(
        op,
        "a second handle onto a tainted buffer is created here; this "
        "analysis tracks taint per SSA value and models no aliasing, so "
        "stores through one handle are not seen through the other");
    return;
  }
}

// Interprocedural flow is not modeled (readme's "interprocedural analysis"
// limitation). A tainted argument crossing a call boundary previously just
// produced clean results, i.e. a call laundered the secret silently.
void visitCall(Operation *op) {

  if (!isa<func::CallOp, func::CallIndirectOp>(op))
    return;

  for (Value operand : op->getOperands()) {
    if (!isTainted(operand))
      continue;
    reportUnknown(
        op,
        "a tainted value crosses a call boundary; this analysis is "
        "intraprocedural, so what the callee does with it is not modeled");
    return;
  }
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
