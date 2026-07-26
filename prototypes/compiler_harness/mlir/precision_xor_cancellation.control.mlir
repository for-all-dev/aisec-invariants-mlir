// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// case: precision-control/value-cancellation
// classification: seeded-semantic-harness
// c source: ../c/precision_controls.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/test/Transforms/InstCombine/xor.ll
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret, declared by sps.label on the argument
// public: the sps.sink_class public store target
// expected outcome: verified
// observer/model: public-sink-value
// reason id: lane-equal-value-after-cancellation
// outstanding obligations: none
// evidence boundary: L1 records RelationalRequired at the store because a
// forward Low/High lattice cannot see value congruence; L2 decides equal stored
// words in the exact product. No L3 or L4 claim.
//
// This is a NEGATIVE CONTROL. The stored value is secret-DEPENDENT by
// dependence and secret-INDEPENDENT by value: both lanes store zero. A forward
// two-label lattice necessarily reports High here, which is exactly the
// imprecision this fixture pins.
//
// The correct structural fix is a value-congruence facility alongside the
// Low/High lattice, not a weakening of the label join. Measured with mlir-opt
// 17.0.6: --canonicalize does NOT fold llvm.xor %a, %a, so the tool will not
// discharge this on the harness's behalf and the control stays meaningful.
//
// CHECK-LABEL: llvm.func @xor_cancellation_control
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: %[[CANCELLED:[0-9]+]] = llvm.xor %[[SECRET:.*]], %[[SECRET]]
// CHECK: llvm.store %[[CANCELLED]], %{{.*}} {sps.sink_class = "public"}
//
// STABLE: llvm.xor %[[S:.*]], %[[S]]
module {
  llvm.func @xor_cancellation_control(
      %secret: i32 {sps.label = "high"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %cancelled = llvm.xor %secret, %secret : i32
    llvm.store %cancelled, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
