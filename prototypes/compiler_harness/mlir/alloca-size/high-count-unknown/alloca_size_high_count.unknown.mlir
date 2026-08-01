// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// scope note: configuration binding supplies no world-structural size binding for the
// allocation; preflight diagnostic reaches the allocation site and stops. No exact product conclusion.
//
// Covers the section 20 acceptance row requiring a refusal when a reachable
// allocation's actual byte size is missing, unproved, or High-dependent.
//
// Rev4 requires the actual byte-size expression to be world-structural. This is
// a universal semantic-support premise, not an optional observer configuration.
//
// THE TRAP THIS EXISTS TO CATCH: both candidate sizes, 64 and 128, lie under one
// public upper bound. An equal CAP does not make the actual size equal. An
// implementation that discharges this by clamping to the cap, or by treating a
// public bound as proof of equal size, is wrong. Cap-based checking is the
// natural first implementation, which is why the paired acceptance twin
// mlir/alloca-size/public-control/alloca_size_public.control.mlir must also stay
// green: a checker that refuses every dynamic allocation would satisfy this
// fixture and fail that one.
//
// WHY Unknown RATHER THAN Counterexample: failure of the world-structural alloca premise
// is a normative refusal. It is not by itself a replayed Bad execution.
//
// INDEPENDENCE NOTE: the world-structural allocation obligation is an
// independent universal semantic-support obligation, not a consequence of
// universal definedness, so it must be tracked as its own binding rather than
// folded into a definedness check.
//
// CHECK-LABEL: llvm.func @alloca_size_high_count
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: %[[SMALL:[0-9]+]] = llvm.mlir.constant(64 : i32) : i32
// CHECK: %[[LARGE:[0-9]+]] = llvm.mlir.constant(128 : i32) : i32
// CHECK: %[[COUNT:[0-9]+]] = llvm.select %{{.*}}, %[[SMALL]], %[[LARGE]]
// CHECK: %[[SCRATCH:[0-9]+]] = llvm.alloca %[[COUNT]] x i8
// CHECK: llvm.store %{{.*}}, %[[SCRATCH]]
//
// The secret-selected size operand must survive, or the fixture stops pinning a
// High-dependent allocation.
// STABLE: llvm.select
// STABLE: llvm.alloca
module {
  llvm.func @alloca_size_high_count(
      %secret_bit: i1 {sps.label = "high"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %small = llvm.mlir.constant(64 : i32) : i32
    %large = llvm.mlir.constant(128 : i32) : i32
    %marker = llvm.mlir.constant(0 : i8) : i8
    %count = llvm.select %secret_bit, %small, %large : i1, i32
    %scratch = llvm.alloca %count x i8 : (i32) -> !llvm.ptr
    llvm.store %marker, %scratch : i8, !llvm.ptr
    %zero = llvm.mlir.constant(0 : i32) : i32
    llvm.store %zero, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
