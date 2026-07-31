// RUN: %mlir-opt %s | %FileCheck %s
//
// case: metatheory/MT-CM5-missing-alias-binding
// entry: abi_alias_missing_binding
// classification: seeded-semantic-harness
// c source: ../c/abi_alias_unproved.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/test/Analysis/BasicAA/noalias-scope-decl.ll
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret, declared by sps.label on the argument
// public: the sps.sink_class public output target
// diagnostic focus: public-sink-value
// evidence boundary: L0 supplies no proved separation clause for %p and %q, so
// L1 cannot close the store-to-load edge and no L2 conclusion follows.
//
// Countermodel MT-CM5, which refutes the invalid principle "unproved ABI alias
// separation may be assumed".
//
// The secret is stored through %p and a value is reloaded through %q, then sent
// to a public output. The ABI sidecar intentionally omits the complete alias
// topology, so neither overlapping nor disjoint calls are admitted precisely.
//
// Merely naming two buffers differently establishes neither choice.
// PublicAliasTopology is a conjunct of LowEq^0, and EntryABIConforms must
// include the COMPLETE alias relation.
//
// WHY THIS IS unknown: a replay needs a complete ABI relation. The paired
// abi_alias_mayalias_overlap.bad fixture admits p==q and yields a counterexample;
// abi_alias_disjoint.control admits only disjoint roots and is the positive twin.
//
// DELIBERATE TRAP: distinct !llvm.ptr arguments and distinct SSA names establish
// no separation. There is intentionally no alias attribute here; policy must be
// supplied by the independent ABI sidecar and bound to frozen bitcode.
//
// CHECK-LABEL: llvm.func @abi_alias_missing_binding
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: llvm.store %{{.*}}, %[[P:.*]] {sps.label = "high"}
// CHECK: %[[V:[0-9]+]] = llvm.load %[[Q:.*]] :
// CHECK: llvm.store %[[V]], %{{.*}} {sps.sink_class = "public"}
module {
  llvm.func @abi_alias_missing_binding(
      %secret: i32 {sps.label = "high"},
      %p: !llvm.ptr,
      %q: !llvm.ptr,
      %public_output: !llvm.ptr {sps.sink_class = "public"}) {
    llvm.store %secret, %p {sps.label = "high"} : i32, !llvm.ptr
    %reloaded = llvm.load %q : !llvm.ptr -> i32
    llvm.store %reloaded, %public_output {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
