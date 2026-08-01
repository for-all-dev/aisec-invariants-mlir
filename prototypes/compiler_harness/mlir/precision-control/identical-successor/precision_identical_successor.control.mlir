// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// scope note: the unary scanner flags a relational review site; a future
// Section-10 diagnostic must defer the proof question to the exact product.
//
// This is a NEGATIVE CONTROL. It is release-relative noninterferent: the secret
// condition selects between two edges that target one block, so no
// coalition-visible control location differs. Section 11 disjunct 2 ("next
// control locations differ") cannot fire when the successor set is a singleton.
//
// A future SPS analysis that reports a violation here is imprecise, not
// correct. The imprecision MUST NOT be repaired by the rule "identical
// successors imply no control leak": the paired anti-control
// mlir/predecessor-choice/blockarg-bad/predecessor_choice_blockarg.bad.mlir
// canonicalizes to this same successor shape and differs only in its
// block-argument operands. Nor may it be repaired
// by treating a diagnostic disposition as proof-authoritative.
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
