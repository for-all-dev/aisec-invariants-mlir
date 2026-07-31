// RUN: %mlir-opt %s | %FileCheck %s
//
// case: acceptance/proved-disjoint-alias-topology
// entry: abi_alias_disjoint_control
// classification: seeded-semantic-harness
// c source: ../c/abi_alias_unproved.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/test/Analysis/BasicAA/noalias-scope-decl.ll
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret, declared by sps.label on the argument
// public: complete Disjoint ABI topology and the public output target
// diagnostic focus: public-sink-value
// evidence boundary: L0 independently binds disjoint p and q;
// L2 therefore keeps q's public initial bytes independent of the secret store.
//
// CHECK-LABEL: llvm.func @abi_alias_disjoint_control
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK-SAME: {{.*}}sps.alias_candidate = "disjoint"
// CHECK: llvm.store %{{.*}}, %[[P:.*]] {sps.label = "high"}
// CHECK: %[[V:[0-9]+]] = llvm.load %[[Q:.*]] :
// CHECK: llvm.store %[[V]], %{{.*}} {sps.sink_class = "public"}
module {
  llvm.func @abi_alias_disjoint_control(
      %secret: i32 {sps.label = "high"},
      %p: !llvm.ptr {sps.alias_candidate = "disjoint"},
      %q: !llvm.ptr {sps.alias_candidate = "disjoint"},
      %public_output: !llvm.ptr {sps.sink_class = "public"}) {
    llvm.store %secret, %p {sps.label = "high"} : i32, !llvm.ptr
    %reloaded = llvm.load %q : !llvm.ptr -> i32
    llvm.store %reloaded, %public_output {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
