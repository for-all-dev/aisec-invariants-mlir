// RUN: %mlir-opt %s | %FileCheck %s
//
// case: metatheory/MT-CM5-unproved-alias-separation
// classification: seeded-semantic-harness
// c source: ../c/abi_alias_unproved.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/test/Analysis/BasicAA/noalias-scope-decl.ll
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret, declared by sps.label on the argument
// public: the sps.sink_class public output target
// expected outcome: unknown
// observer/model: public-sink-value
// reason id: alias-binding-mismatch
// outstanding obligations: proved-disjoint-clause
// evidence boundary: L0 supplies no proved separation clause for %p and %q, so
// L1 cannot close the store-to-load edge and no L2 conclusion follows.
//
// Countermodel MT-CM5, which refutes the invalid principle "unproved ABI alias
// separation may be assumed".
//
// The secret is stored through %p and a value is reloaded through %q, then sent
// to a public output. An analysis that ASSUMES %p and %q are disjoint leaves the
// abstract %q object untouched and proves a constant output. In an admitted
// concrete call with %p equal to %q, the store updates the byte read through
// %q, and two secret values produce two public outputs.
//
// Merely naming two buffers differently establishes neither choice.
// PublicAliasTopology is a conjunct of LowEq^0, and EntryABIConforms must
// include the COMPLETE alias relation.
//
// WHY THIS IS unknown RATHER THAN unsafe: with no proved Disjoint clause and no
// declared MayAlias realization in the product, neither safety nor a replayable
// counterexample follows. Asserting unsafe here would itself be unsound, because
// a counterexample requires a witness replayed by the exact semantics. The two
// sound repairs are to put the alias into the product so it can be caught, or to
// put disjointness into the ABI admission contract and open a deployment
// obligation.
//
// DELIBERATE TRAP: a first implementation will almost certainly assume two
// distinct !llvm.ptr arguments are disjoint. The sps.alias attributes below
// declare MayAlias explicitly, and no llvm.noalias is present to be
// misinterpreted as a licence.
//
// CHECK-LABEL: llvm.func @abi_alias_unproved
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK-SAME: {{.*}}sps.alias = "may_alias_q"
// CHECK-SAME: {{.*}}sps.alias = "may_alias_p"
// CHECK: llvm.store %{{.*}}, %[[P:.*]] {sps.label = "high"}
// CHECK: %[[V:[0-9]+]] = llvm.load %[[Q:.*]] :
// CHECK: llvm.store %[[V]], %{{.*}} {sps.sink_class = "public"}
module {
  llvm.func @abi_alias_unproved(
      %secret: i32 {sps.label = "high"},
      %p: !llvm.ptr {sps.alias = "may_alias_q"},
      %q: !llvm.ptr {sps.alias = "may_alias_p"},
      %public_output: !llvm.ptr {sps.sink_class = "public"}) {
    llvm.store %secret, %p {sps.label = "high"} : i32, !llvm.ptr
    %reloaded = llvm.load %q : !llvm.ptr -> i32
    llvm.store %reloaded, %public_output {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
