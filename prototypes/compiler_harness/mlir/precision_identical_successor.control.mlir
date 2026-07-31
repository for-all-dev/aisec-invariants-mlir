// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// case: precision-control/identical-successor
// entry: identical_successor_control
// classification: seeded-semantic-harness
// c source: ../c/precision_controls.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/mlir/test/Analysis/DataFlow/test-dead-code-analysis.mlir
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %high_condition, declared by sps.label on the argument
// public: the stored constant 7 and the sps.sink_class public store target
// diagnostic focus: source-control-location-trace
// diagnostic disposition: relational-required
// evidence boundary: L1 records RelationalRequired at the branch site because
// the section 10 diagnostic has no proof-authoritative strong update; L2
// decides equal control locations in the exact product. No L3 or L4 claim.
//
// This is a NEGATIVE CONTROL. It is release-relative noninterferent: the secret
// condition selects between two edges that target one block, so no
// coalition-visible control location differs. Section 11 disjunct 2 ("next
// control locations differ") cannot fire when the successor set is a singleton.
//
// A future SPS analysis that reports a violation here is imprecise, not
// correct. The imprecision MUST NOT be repaired by the rule "identical
// successors imply no control leak": the paired anti-control
// predecessor_choice_blockarg.bad.mlir canonicalizes to this same successor
// shape and differs only in its block-argument operands. Nor may it be repaired
// by StaticallyDischarged or NotObservable, which cannot establish Proved.
//
// CHECK-LABEL: llvm.func @identical_successor_control
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK-SAME: {{.*}}sps.sink_class = "public"
// CHECK: %[[VALUE:[0-9]+]] = llvm.mlir.constant(7 : i32) : i32
// CHECK: llvm.cond_br %{{.*}}, ^[[MERGE:bb[0-9]+]], ^[[MERGE]]
// CHECK: ^[[MERGE]]:
// CHECK: llvm.store %[[VALUE]], %{{.*}} {sps.sink_class = "public"}
//
// The second RUN pins that the shape is stable under canonicalization, so the
// control cannot silently decay into a different scenario.
// STABLE: llvm.cond_br %{{.*}}, ^[[M:bb[0-9]+]], ^[[M]]
module {
  llvm.func @identical_successor_control(
      %high_condition: i1 {sps.label = "high"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %public_value = llvm.mlir.constant(7 : i32) : i32
    llvm.cond_br %high_condition, ^merge, ^merge
  ^merge:
    llvm.store %public_value, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
