// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: configuration binding independently binds disjoint p and q;
// exact product therefore keeps q's public initial bytes independent of the secret store.
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
