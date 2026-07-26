// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// case: precision-control/public-overwrite-before-observation
// classification: seeded-semantic-harness
// c source: ../c/precision_controls.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/test/Transforms/DeadStoreElimination/simple.ll
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret, declared by sps.label on the argument
// public: %public_count, %public_value, and the sps.sink_class store target
// expected outcome: verified
// observer/model: public-sink-value
// reason id: public-overwrite-before-observation
// outstanding obligations: none
// evidence boundary: L1 records RelationalRequired at the reload because
// section 10 forbids a proof-authoritative strong update in the diagnostic
// layer; L2 decides equal reloaded words in the exact product. No L3 or L4.
//
// This is a NEGATIVE CONTROL. The secret is stored into a stack slot and then
// fully overwritten by a public value before any load, so the reloaded word is
// identical in both lanes.
//
// Only a strong update discharges this statically, and SPS Rev-4 section 10
// states the diagnostic analysis has "no proof-authoritative strong update, no
// summaries, and no slice selection". The required L1 disposition is therefore
// RelationalRequired, NOT silence, and the kill/gen reasoning belongs in the
// product layer only. An implementation that adds a strong update to the
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
