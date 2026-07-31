// RUN: %mlir-opt %s | %FileCheck %s
//
// case: metatheory/MT-CM5-mayalias-overlap
// entry: abi_alias_mayalias_overlap
// classification: seeded-semantic-harness
// c source: ../c/abi_alias_unproved.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/test/Analysis/BasicAA/noalias-scope-decl.ll
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret, declared by sps.label on the argument
// public: complete MayAlias ABI topology and the public output target
// diagnostic focus: public-sink-value
// evidence boundary: the independent ABI sidecar admits p==q; L2 replays that
// realization and two secret values yield two public output values.
//
// The sps.alias_candidate attributes are documentary locators only. The checked
// ABI sidecar, not the IR, authorizes the overlapping realization.
//
// CHECK-LABEL: llvm.func @abi_alias_mayalias_overlap
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK-SAME: {{.*}}sps.alias_candidate = "may-alias"
// CHECK: llvm.store %{{.*}}, %[[P:.*]] {sps.label = "high"}
// CHECK: %[[V:[0-9]+]] = llvm.load %[[Q:.*]] :
// CHECK: llvm.store %[[V]], %{{.*}} {sps.sink_class = "public"}
module {
  llvm.func @abi_alias_mayalias_overlap(
      %secret: i32 {sps.label = "high"},
      %p: !llvm.ptr {sps.alias_candidate = "may-alias"},
      %q: !llvm.ptr {sps.alias_candidate = "may-alias"},
      %public_output: !llvm.ptr {sps.sink_class = "public"}) {
    llvm.store %secret, %p {sps.label = "high"} : i32, !llvm.ptr
    %reloaded = llvm.load %q : !llvm.ptr -> i32
    // CONFIDENTIALITY ERROR: admitted overlapping roots expose the secret
    // secret source: %secret is stored through p
    // observable effect: when p equals q, public_output receives the secret
    // reason: MayAlias requires the overlapping realization to remain in the product
    // detection boundary: exact byte-memory L2 product and witness replay
    llvm.store %reloaded, %public_output {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
