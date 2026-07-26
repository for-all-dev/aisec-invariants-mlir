// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: metatheory/MT-CM6-predecessor-choice
// classification: seeded-semantic-harness
// c source: ../c/predecessor_choice_blockarg_bad.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Analysis/DataFlow/test-dead-code-analysis.mlir
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret_bit, declared by sps.label on the argument
// public: the arm constants 10 and 20, and the sps.sink_class store target
// expected outcome: unsafe
// observer/model: public-sink-value
// reason id: secret-selected-block-argument
// outstanding obligations: none
// evidence boundary: L1 must close dependence over predecessor choice, not only
// over SSA operand edges; L2 replays secret_bit=0 against secret_bit=1 and
// observes stored words 20 against 10. No L3 or L4 claim.
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
// PAIRED ANTI-CONTROL for precision_identical_successor.control.mlir. Both are
// llvm.cond_br into ONE successor block; they differ only in whether the edges
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
// CHECK-LABEL: llvm.func @predecessor_choice_blockarg_bad
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: %[[LOW:[0-9]+]] = llvm.mlir.constant(10 : i32) : i32
// CHECK: %[[HIGH:[0-9]+]] = llvm.mlir.constant(20 : i32) : i32
// CHECK: llvm.cond_br %{{.*}}, ^[[MERGE:bb[0-9]+]](%[[LOW]] : i32), ^[[MERGE]](%[[HIGH]] : i32)
// CHECK: ^[[MERGE]](%[[SELECTED:[0-9]+]]: i32):
// CHECK: llvm.store %[[SELECTED]], %{{.*}} {sps.sink_class = "public"}
//
// Already canonical: the differing block-argument operands must survive, or the
// fixture decays into its own paired control and stops testing anything.
// STABLE: llvm.cond_br %{{.*}}, ^[[M:bb[0-9]+]](%{{.*}} : i32), ^[[M]](%{{.*}} : i32)
module {
  llvm.func @predecessor_choice_blockarg_bad(
      %secret_bit: i1 {sps.label = "high"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %low = llvm.mlir.constant(10 : i32) : i32
    %high = llvm.mlir.constant(20 : i32) : i32
    // CONFIDENTIALITY ERROR: secret selects the merge block argument
    // secret source: %secret_bit chooses which predecessor edge reaches ^merge
    // observable effect: the public sink receives 10 or 20 according to the secret
    // reason: dependence closed only over SSA operands misses the predecessor gating fact
    // detection boundary: L1 predecessor-choice closure over block arguments
    // expected-error @+1 {{secret-selected-block-argument}}
    llvm.cond_br %secret_bit, ^merge(%low : i32), ^merge(%high : i32)
  ^merge(%selected: i32):
    llvm.store %selected, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
