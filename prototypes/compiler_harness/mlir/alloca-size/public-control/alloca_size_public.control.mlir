// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// scope note: configuration binding supplies the world-structural size binding; preflight diagnostic confirms
// the allocation size derives only from it. No compiler-conformance evidence or deployment evidence claim.
//
// ACCEPTANCE TWIN for
// mlir/alloca-size/high-count-unknown/alloca_size_high_count.unknown.mlir. Same
// allocation skeleton, dynamic in exactly the same way, but the byte count is public and
// names a candidate world-structural size root. The independent ABI sidecar and
// future conformant bitcode and its canonical ABI must validate the binding; this attribute alone never
// establishes it.
//
// WHY THIS FIXTURE IS NOT OPTIONAL: a refusal-only corpus is satisfied by a
// checker that refuses every dynamic allocation. This twin is what makes the
// paired refusal meaningful. The two differ only in the label and binding on the
// size operand, so an implementation cannot satisfy both by inspecting the
// allocation shape alone; it must read the configuration binding declaration.
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
