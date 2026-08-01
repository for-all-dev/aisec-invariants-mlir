// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --canonicalize | %FileCheck %s --check-prefix=STABLE
//
// scope note: the unary scanner may collect byte regions for review, but only
// the eventual exact product can decide byte-exact disjointness.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// This is a NEGATIVE CONTROL. The secret lands at byte offset 4 and the public
// sink is fed only from byte offset 8, so the observed word is equal in both
// lanes under the V2 exact-address model, which section 4.1 fixes as
// StableAllocationExactByteOffsetV2: exact allocation identity plus exact byte
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
// CHECK-SAME: {{.*}}sps.component_ref = "secret-byte"
// CHECK-SAME: sps.fixture_refs = ["secret:secret_byte"]
// CHECK-SAME: sps.label = "high"
// CHECK-SAME: {{.*}}sps.abi_root_ref = "buffer"
// CHECK-SAME: {{.*}}sps.fixture_refs = ["public-memory:public_sink"]
// CHECK: %[[OFF_SECRET:[0-9]+]] = llvm.mlir.constant(4 : i32) : i32
// CHECK: %[[OFF_PUBLIC:[0-9]+]] = llvm.mlir.constant(8 : i32) : i32
// CHECK: %[[SECRET_SLOT:[0-9]+]] = llvm.getelementptr %{{.*}}[%[[OFF_SECRET]]]
// CHECK: %[[PUBLIC_SLOT:[0-9]+]] = llvm.getelementptr %{{.*}}[%[[OFF_PUBLIC]]]
// CHECK: llvm.store %{{.*}}, %[[SECRET_SLOT]] {sps.fixture_refs = ["store:secret-offset-4"], sps.label = "high", sps.site_alias = "secret-offset-4"}
// CHECK: llvm.store %{{.*}}, %[[PUBLIC_SLOT]] {sps.fixture_refs = ["store:public-offset-8"], sps.label = "public", sps.site_alias = "public-offset-8"}
// CHECK: %[[RELOADED:[0-9]+]] = llvm.load %[[PUBLIC_SLOT]]
// CHECK: llvm.store %[[RELOADED]], %{{.*}} {sps.fixture_refs = ["store:public-reload-output"], sps.sink_class = "public", sps.site_alias = "public-reload-output"}
//
// Both nonzero offsets must survive canonicalization or the control is void.
// Measured with mlir-opt 17.0.6: canonicalization folds the constant operands
// into STATIC getelementptr indices, so the two byte offsets remain distinct and
// become statically visible rather than disappearing. Assert that stronger form.
// STABLE: llvm.getelementptr %{{.*}}[4] : (!llvm.ptr) -> !llvm.ptr, i8
// STABLE: llvm.getelementptr %{{.*}}[8] : (!llvm.ptr) -> !llvm.ptr, i8
// STABLE: llvm.store %{{.*}} {sps.fixture_refs = ["store:secret-offset-4"], sps.label = "high", sps.site_alias = "secret-offset-4"}
// STABLE: llvm.store %{{.*}} {sps.fixture_refs = ["store:public-offset-8"], sps.label = "public", sps.site_alias = "public-offset-8"}
module {
  llvm.func @offset_disjoint_control(
      %secret_byte: i32 {
        sps.component_ref = "secret-byte",
        sps.fixture_refs = ["secret:secret_byte"],
        sps.label = "high"},
      %public_value: i32 {sps.label = "public"},
      %buffer: !llvm.ptr {sps.abi_root_ref = "buffer", sps.label = "public"},
      %public_sink: !llvm.ptr {
        sps.fixture_refs = ["public-memory:public_sink"],
        sps.output_ref = "public-sink",
        sps.sink_class = "public"}) {
    %off_secret = llvm.mlir.constant(4 : i32) : i32
    %off_public = llvm.mlir.constant(8 : i32) : i32
    %secret_slot = llvm.getelementptr %buffer[%off_secret] : (!llvm.ptr, i32) -> !llvm.ptr, i8
    %public_slot = llvm.getelementptr %buffer[%off_public] : (!llvm.ptr, i32) -> !llvm.ptr, i8
    llvm.store %secret_byte, %secret_slot {
      sps.fixture_refs = ["store:secret-offset-4"],
      sps.label = "high",
      sps.site_alias = "secret-offset-4"
    } : i32, !llvm.ptr
    llvm.store %public_value, %public_slot {
      sps.fixture_refs = ["store:public-offset-8"],
      sps.label = "public",
      sps.site_alias = "public-offset-8"
    } : i32, !llvm.ptr
    %reloaded = llvm.load %public_slot : !llvm.ptr -> i32
    llvm.store %reloaded, %public_sink {
      sps.fixture_refs = ["store:public-reload-output"],
      sps.sink_class = "public",
      sps.site_alias = "public-reload-output"
    } : i32, !llvm.ptr
    llvm.return
  }
}
