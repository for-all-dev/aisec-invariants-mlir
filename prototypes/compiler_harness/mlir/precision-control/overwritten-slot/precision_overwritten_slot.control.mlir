// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// scope note: the unary scanner flags a relational review site at the reload;
// the eventual exact product decides whether the reloaded words are equal.
//
// This is a NEGATIVE CONTROL. The secret is stored into a stack slot and then
// fully overwritten by a public value before any load, so the reloaded word is
// identical in both lanes.
//
// Only a strong update discharges this statically, and SPS Rev-4 section 10
// states the diagnostic analysis has "no proof-authoritative strong update, no
// summaries, and no slice selection". This preflight therefore records only a
// relational candidate; the kill/gen reasoning belongs in the exact product.
// An implementation that adds a proof-authoritative strong update to the
// diagnostic layer to make this fixture quiet has become unsound; that is the
// specific regression this control guards.
//
// Measured with mlir-opt 17.0.6: --canonicalize does NOT eliminate either store
// to the slot, so the overwrite shape survives and the control stays meaningful.
//
// CHECK-LABEL: llvm.func @overwritten_slot_control
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: %[[SLOT:[0-9]+]] = llvm.alloca
// CHECK: llvm.store %{{.*}}, %[[SLOT]] {sps.label = "high"}
// CHECK: llvm.store %{{.*}}, %[[SLOT]] {sps.label = "public"}
// CHECK: %[[RELOADED:[0-9]+]] = llvm.load %[[SLOT]]
// CHECK: llvm.store %[[RELOADED]], %{{.*}} {sps.sink_class = "public"}
//
// STABLE: llvm.alloca
// STABLE: llvm.store
// STABLE: llvm.store
// STABLE: llvm.load
module {
  llvm.func @overwritten_slot_control(
      %secret: i32 {sps.label = "high"},
      %public_count: i32 {sps.label = "public"},
      %public_value: i32 {sps.label = "public"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %slot = llvm.alloca %public_count x i32 : (i32) -> !llvm.ptr
    llvm.store %secret, %slot {sps.label = "high"} : i32, !llvm.ptr
    llvm.store %public_value, %slot {sps.label = "public"} : i32, !llvm.ptr
    %reloaded = llvm.load %slot : !llvm.ptr -> i32
    llvm.store %reloaded, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
