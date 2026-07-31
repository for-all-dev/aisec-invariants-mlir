// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// case: precision-control/offset-disjoint-public-reload
// entry: offset_disjoint_control
// classification: seeded-semantic-harness
// c source: ../c/precision_controls.c
// upstream GitHub source: https://github.com/llvm/llvm-project/blob/173476ea0407cc037134370a651bb71e9f2dac04/llvm/test/Analysis/BasicAA/gep-alias.ll
// upstream revision: 173476ea0407cc037134370a651bb71e9f2dac04
// secret: %secret_byte, declared by sps.label on the argument
// public: %public_value, byte offsets 4 and 8, and the public store target
// diagnostic focus: public-sink-value
// diagnostic disposition: relational-required
// evidence boundary: L1 may collect byte regions for diagnostics but section 10
// states those are not proof certificates, so the site is RelationalRequired;
// L2 decides byte-exact disjointness in the exact product. No L3 or L4 claim.
//
// This is a NEGATIVE CONTROL. The secret lands at byte offset 4 and the public
// sink is fed only from byte offset 8, so the observed word is equal in both
// lanes under the v1 address model, which section 4.1 fixes as
// StableAllocationExactByteOffsetV1: exact allocation identity plus exact byte
// offset, with no masking, bucketing, or cache-line coarsening.
//
// Two design facts this pins:
//   1. A memory map keyed at allocation granularity cannot discharge this and
//      will report a false violation.
//   2. A map that coarsens offsets must NOT report Proved here either. Under
//      section 20 row 10 a configured offset class that discards any
//      allocation-relative byte bit is Unknown(UnsupportedAddressObservationProfile)
//      and never Proved. Silence obtained by coarsening is the wrong repair.
//
// Offsets are deliberately nonzero. Measured with mlir-opt 17.0.6: a
// getelementptr with a constant 0 index folds away to the base pointer, which
// would erase the shape this fixture exists to pin.
//
// CHECK-LABEL: llvm.func @offset_disjoint_control
// CHECK-SAME: {{.*}}sps.label = "high"
// CHECK: %[[OFF_SECRET:[0-9]+]] = llvm.mlir.constant(4 : i32) : i32
// CHECK: %[[OFF_PUBLIC:[0-9]+]] = llvm.mlir.constant(8 : i32) : i32
// CHECK: %[[SECRET_SLOT:[0-9]+]] = llvm.getelementptr %{{.*}}[%[[OFF_SECRET]]]
// CHECK: %[[PUBLIC_SLOT:[0-9]+]] = llvm.getelementptr %{{.*}}[%[[OFF_PUBLIC]]]
// CHECK: llvm.store %{{.*}}, %[[SECRET_SLOT]] {sps.label = "high"}
// CHECK: llvm.store %{{.*}}, %[[PUBLIC_SLOT]] {sps.label = "public"}
// CHECK: %[[RELOADED:[0-9]+]] = llvm.load %[[PUBLIC_SLOT]]
// CHECK: llvm.store %[[RELOADED]], %{{.*}} {sps.sink_class = "public"}
//
// Both nonzero offsets must survive canonicalization or the control is void.
// Measured with mlir-opt 17.0.6: canonicalization folds the constant operands
// into STATIC getelementptr indices, so the two byte offsets remain distinct and
// become statically visible rather than disappearing. Assert that stronger form.
// STABLE: llvm.getelementptr %{{.*}}[4] : (!llvm.ptr) -> !llvm.ptr, i8
// STABLE: llvm.getelementptr %{{.*}}[8] : (!llvm.ptr) -> !llvm.ptr, i8
// STABLE: llvm.store %{{.*}} {sps.label = "high"}
// STABLE: llvm.store %{{.*}} {sps.label = "public"}
module {
  llvm.func @offset_disjoint_control(
      %secret_byte: i32 {sps.label = "high"},
      %public_value: i32 {sps.label = "public"},
      %buffer: !llvm.ptr {sps.label = "public", sps.alias_candidate = "disjoint_v1"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %off_secret = llvm.mlir.constant(4 : i32) : i32
    %off_public = llvm.mlir.constant(8 : i32) : i32
    %secret_slot = llvm.getelementptr %buffer[%off_secret] : (!llvm.ptr, i32) -> !llvm.ptr, i8
    %public_slot = llvm.getelementptr %buffer[%off_public] : (!llvm.ptr, i32) -> !llvm.ptr, i8
    llvm.store %secret_byte, %secret_slot {sps.label = "high"} : i32, !llvm.ptr
    llvm.store %public_value, %public_slot {sps.label = "public"} : i32, !llvm.ptr
    %reloaded = llvm.load %public_slot : !llvm.ptr -> i32
    llvm.store %reloaded, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
