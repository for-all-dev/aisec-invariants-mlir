// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// scope note: the unary scanner flags a relational review site because its
// taint abstraction cannot see value congruence; the exact product decides it.
//
// This is a NEGATIVE CONTROL. The stored value is secret-DEPENDENT by
// dependence and secret-INDEPENDENT by value: both lanes store zero. A forward
// unary taint abstraction necessarily flags the value here, which is exactly
// the imprecision this fixture pins.
//
// A more precise preflight may add a non-authoritative value-congruence aid;
// it must not weaken the eventual coalition-indexed product. Measured with mlir-opt
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
