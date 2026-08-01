// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: the independent ABI sidecar admits p==q; exact product replays that
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
    // PREFLIGHT FINDING: admitted overlapping roots expose the secret
    // secret source: %secret is stored through p
    // observable effect: when p equals q, public_output receives the secret
    // reason: MayAlias requires the overlapping realization to remain in the product
    // preflight expectation: preserve the store/load/public-sink shape for later ABI binding
    llvm.store %reloaded, %public_output {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
