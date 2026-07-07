//===- VerifyNonInterference.cpp - Secret non-interference verifier -----===//
//
// Implements the `aisec-verify-non-interference` pass.
//
// Walks forward from function arguments carrying the `aisec.protected` unit
// attribute, propagating "taint" through SSA uses and through the body regions
// of `secret.generic` ops. Any `secret.reveal` reached during this walk must
// itself carry the `aisec.declassify` unit attribute — otherwise the pass
// reports an error.
//
// Design notes (MVP scope):
//   - Taint is propagated conservatively: if ANY operand of an op is tainted,
//     ALL of its results become tainted. This over-approximates (imprecise
//     but sound) and keeps the analysis simple.
//   - For `secret.generic`, operands become block arguments of the body, and
//     yielded values become results. We taint both the block arguments
//     corresponding to tainted operands and (conservatively) all results when
//     any operand is tainted.
//   - Control-flow merges through block arguments of successor blocks are NOT
//     currently handled. This is a known gap for any non-trivial function
//     body.
//
// Affine-flow check:
//   In addition to the non-interference walk, the pass enforces a simple
//   affine-use rule on every protected function argument: each such argument
//   must have at most one direct SSA user. Multi-use is rejected as a
//   fan-out leak — a single secret reaching two distinct downstream channels
//   is the canonical amplification vector. This is the syntactic, conservative
//   form of the property; a precise version would track output-reaching uses
//   transitively.
//
//===----------------------------------------------------------------------===//

#include "AISec/Transforms/Passes.h"

#include "lib/Dialect/Secret/IR/SecretDialect.h"
#include "lib/Dialect/Secret/IR/SecretOps.h"
#include "lib/Dialect/Secret/IR/SecretTypes.h"

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/BuiltinAttributes.h"
#include "mlir/IR/Operation.h"
#include "mlir/IR/Value.h"
#include "mlir/Pass/Pass.h"
#include "llvm/ADT/DenseSet.h"
#include "llvm/ADT/SmallVector.h"

namespace mlir::aisec {

#define GEN_PASS_DEF_VERIFYNONINTERFERENCEPASS
#include "AISec/Transforms/Passes.h.inc"

namespace {

constexpr llvm::StringLiteral kProtectedAttr = "aisec.protected";
constexpr llvm::StringLiteral kDeclassifyAttr = "aisec.declassify";

class VerifyNonInterferencePass
    : public impl::VerifyNonInterferencePassBase<VerifyNonInterferencePass> {
 public:
  using VerifyNonInterferencePassBase::VerifyNonInterferencePassBase;

  void runOnOperation() override {
    func::FuncOp func = getOperation();

    // 1. Collect SSA values seeded by `aisec.protected` function arguments.
    llvm::DenseSet<Value> tainted;
    llvm::SmallVector<Value> worklist;
    for (unsigned i = 0, e = func.getNumArguments(); i < e; ++i) {
      if (!func.getArgAttr(i, kProtectedAttr)) continue;
      Value arg = func.getArgument(i);

      // 1a. Affine-flow check. A protected secret with
      // more than one direct user is a fan-out leak — even if every consumer
      // happens to be a sanctioned declassify, splitting a single secret
      // across two channels is the textbook amplification vector. Reject
      // syntactically before any transitive walk.
      unsigned numUses = 0;
      for (auto &use : arg.getUses()) {
        (void)use;
        ++numUses;
      }
      if (numUses > 1) {
        func.emitError()
            << "protected secret (function argument #" << i << ") has "
            << numUses
            << " direct uses; affine flow requires at most one — fan-out "
            << "of a secret across multiple channels is a leak even if each "
            << "channel is individually declassified";
        signalPassFailure();
        return;
      }

      if (tainted.insert(arg).second) worklist.push_back(arg);
    }
    if (worklist.empty()) return;  // nothing to verify

    // 2. Forward taint propagation through users.
    while (!worklist.empty()) {
      Value v = worklist.pop_back_val();
      for (Operation *user : v.getUsers()) {
        // Case A: secret.reveal — the policy decision point.
        if (auto reveal = dyn_cast<heir::secret::RevealOp>(user)) {
          if (!reveal->hasAttr(kDeclassifyAttr)) {
            reveal.emitError()
                << "protected secret revealed without declassification; "
                << "add `{aisec.declassify}` to this op if the release is "
                << "intentional and policy-authorized";
            signalPassFailure();
            return;
          }
          // Declassified: stop propagating past this point. The value is
          // leaving the secret domain legitimately.
          continue;
        }

        // Case B: secret.generic — operand becomes a block argument in the
        // body region; yielded values become results.
        if (auto generic = dyn_cast<heir::secret::GenericOp>(user)) {
          // Taint the block argument corresponding to this operand position.
          for (auto [idx, operand] : llvm::enumerate(generic.getOperands())) {
            if (operand != v) continue;
            if (generic.getRegion().empty()) continue;
            Block &entry = generic.getRegion().front();
            if (idx >= entry.getNumArguments()) continue;
            Value blockArg = entry.getArgument(idx);
            if (tainted.insert(blockArg).second) worklist.push_back(blockArg);
          }
          // Conservatively taint all results of the generic — any of them
          // could have flowed from the tainted operand through the body.
          for (Value r : generic.getResults()) {
            if (tainted.insert(r).second) worklist.push_back(r);
          }
          continue;
        }

        // Case C: generic op — taint all of its results.
        for (Value r : user->getResults()) {
          if (tainted.insert(r).second) worklist.push_back(r);
        }
      }
    }
  }
};

}  // namespace
}  // namespace mlir::aisec
