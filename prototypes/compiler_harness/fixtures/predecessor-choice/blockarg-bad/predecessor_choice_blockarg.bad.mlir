// RUN: %checkpoint-runner run --snapshot fixtures/predecessor-choice/blockarg-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/predecessor-choice/blockarg-bad/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/predecessor-choice/blockarg-bad/predecessor_choice_blockarg.bad.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic must close dependence over predecessor choice, not only
// over SSA operand edges; exact product replays secret_bit=0 against secret_bit=1 and
// observes stored words 20 against 10. No compiler-conformance evidence or deployment evidence claim.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// Countermodel MT-CM6 of the SPS Rev-4 metatheory, which refutes the invalid
// principle "an ordinary SSA slice is closed around a phi node". Section 8 is
// the normative rule: "Phi nodes select the incoming value associated with the
// predecessor edge actually taken ... There is no ordinary slicing rule that may
// omit this gating fact."
//
// No secret value flows through any SSA operand: both arms materialize public
// constants. In the LLVM dialect a phi IS a block argument, so a dependence
// relation closed over operand edges sees two constants and wrongly concludes
// there is no flow. This is the single most likely unsoundness in a first
// implementation, which is why it is checked in already-canonical.
//
// PAIRED ANTI-CONTROL for
// fixtures/precision-control/identical-successor/precision_identical_successor.control.mlir.
// Both are llvm.cond_br into ONE successor block; they differ only in whether the edges
// carry differing block-argument operands. Under section 11, Bad_A disjuncts 1
// through 4 hold for this form (one successor, equal statuses, aligned sites),
// so the leak lands only on disjunct 5, the differing projected words at the
// store. Consequence: repairing that control with the rule "identical
// successors imply no control leak" silently accepts THIS leak. Never satisfy
// one of these two fixtures by weakening the other.
//
// The reason id is deliberately not secret-dependent-control-location: the
// control locations do NOT differ here. Only the selected block argument does.
//
//
// Already canonical: the differing block-argument operands must survive, or the
// fixture decays into its own paired control and stops testing anything.
module {
  llvm.func @predecessor_choice_blockarg_bad(
      %secret_bit: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %low = llvm.mlir.constant(10 : i32) : i32
    %high = llvm.mlir.constant(20 : i32) : i32
    %condition = llvm.icmp "ne" %secret_bit, %zero : i32
    // PREFLIGHT FINDING: secret selects the merge block argument
    // secret source: %secret_bit chooses which predecessor edge reaches ^merge
    // observable effect: the public sink receives 10 or 20 according to the secret
    // reason: dependence closed only over SSA operands misses the predecessor gating fact
    // preflight expectation: preflight diagnostic predecessor-choice closure over block arguments
    llvm.cond_br %condition, ^merge(%low : i32), ^merge(%high : i32)
  ^merge(%selected: i32):
    llvm.return {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} %selected : i32
  }
}
