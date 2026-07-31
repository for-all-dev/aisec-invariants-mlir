// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// case: acceptance/world-structural-alloca-size
// entry: alloca_size_public_control
// classification: seeded-semantic-harness
// c source: ../c/alloca_size_models.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/test/Transforms/InstCombine/alloca.ll
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: none reaches the allocation size; the entry declares no High component
// public: %public_count with a validated world-structural size binding
// diagnostic focus: world-structural-control-trace
// evidence boundary: L0 supplies the world-structural size binding; L1 confirms
// the allocation size derives only from it. No L3 or L4 claim.
//
// ACCEPTANCE TWIN for alloca_size_high_count.unknown.mlir. Same allocation
// skeleton, dynamic in exactly the same way, but the byte count is public and
// names a candidate world-structural size root. The independent ABI sidecar and
// future conformant bitcode and its canonical ABI must validate the binding; this attribute alone never
// establishes it.
//
// WHY THIS FIXTURE IS NOT OPTIONAL: a refusal-only corpus is satisfied by a
// checker that refuses every dynamic allocation. This twin is what makes the
// paired refusal meaningful. The two differ only in the label and binding on the
// size operand, so an implementation cannot satisfy both by inspecting the
// allocation shape alone; it must read the L0 declaration.
//
// The discardable attribute is only a locator used by this MLIR shape test. It is
// intentionally named `candidate` so no checker can mistake IR self-annotation
// for the independently authored, hash-bound ABI fact.
//
// CHECK-LABEL: llvm.func @alloca_size_public_control
// CHECK-SAME: {{.*}}sps.label = "public"
// CHECK-SAME: {{.*}}sps.world_structural_candidate = "public_count_v1"
// CHECK: %[[SCRATCH:[0-9]+]] = llvm.alloca %{{.*}} x i8
// CHECK: llvm.store %{{.*}}, %[[SCRATCH]]
// CHECK: llvm.store %{{.*}} {sps.sink_class = "public"}
//
// STABLE: sps.world_structural_candidate = "public_count_v1"
// STABLE: llvm.alloca
module {
  llvm.func @alloca_size_public_control(
      %public_count: i32 {sps.label = "public", sps.world_structural_candidate = "public_count_v1"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %marker = llvm.mlir.constant(0 : i8) : i8
    %scratch = llvm.alloca %public_count x i8 : (i32) -> !llvm.ptr
    llvm.store %marker, %scratch : i8, !llvm.ptr
    %zero = llvm.mlir.constant(0 : i32) : i32
    llvm.store %zero, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
