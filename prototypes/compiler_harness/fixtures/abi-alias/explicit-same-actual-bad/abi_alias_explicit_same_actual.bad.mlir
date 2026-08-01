// RUN: %mlir-opt %s | %FileCheck %s
//
// This fixture makes the overlapping realization explicit in the program: the
// wrapper forwards one SSA pointer to both pointer slots of an internal helper.
// It therefore exercises call-operand identity rather than an independently
// authored ABI-root alias relation.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func internal @abi_alias_explicit_same_actual_helper
// CHECK: llvm.store %{{.*}}, %[[P:.*]] {sps.fixture_refs = ["store:secret-through-helper-p"], sps.label = "high", sps.site_alias = "secret-through-helper-p"}
// CHECK: %[[RELOADED:[0-9]+]] = llvm.load %{{.*}} :
// CHECK: llvm.store %[[RELOADED]], %{{.*}} {sps.fixture_refs = ["store:helper-q-to-public-output"], sps.sink_class = "public", sps.site_alias = "helper-q-to-public-output"}
// CHECK-LABEL: llvm.func @abi_alias_explicit_same_actual
// CHECK-SAME: %[[SECRET:[a-zA-Z0-9_]+]]: i32
// CHECK-SAME: sps.fixture_refs = ["secret:secret"]
// CHECK-SAME: %[[SHARED:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK-SAME: %[[PUBLIC:[a-zA-Z0-9_]+]]: !llvm.ptr
// CHECK-SAME: sps.fixture_refs = ["public-memory:public_output"]
// CHECK: llvm.call @abi_alias_explicit_same_actual_helper(%[[SECRET]], %[[SHARED]], %[[SHARED]], %[[PUBLIC]]) {sps.fixture_refs = ["call:same-actual-p-q"], sps.site_alias = "same-actual-p-q"}
module {
  llvm.func internal @abi_alias_explicit_same_actual_helper(
      %secret: i32 {sps.label = "high"},
      %p: !llvm.ptr,
      %q: !llvm.ptr,
      %public_output: !llvm.ptr {sps.sink_class = "public"}) {
    llvm.store %secret, %p {
      sps.fixture_refs = ["store:secret-through-helper-p"],
      sps.label = "high",
      sps.site_alias = "secret-through-helper-p"
    } : i32, !llvm.ptr
    %reloaded = llvm.load %q : !llvm.ptr -> i32
    // PREFLIGHT FINDING: one actual pointer supplies both helper roots
    // secret source: %secret is stored through the helper's %p parameter
    // observable effect: %public_output receives the value reloaded through %q
    // reason: the wrapper passes %shared in both pointer argument slots
    // preflight expectation: preserve identical call operands for later exact replay
    llvm.store %reloaded, %public_output {
      sps.fixture_refs = ["store:helper-q-to-public-output"],
      sps.sink_class = "public",
      sps.site_alias = "helper-q-to-public-output"
    } : i32, !llvm.ptr
    llvm.return
  }

  llvm.func @abi_alias_explicit_same_actual(
      %secret: i32 {
        sps.component_ref = "secret",
        sps.fixture_refs = ["secret:secret"],
        sps.label = "high"},
      %shared: !llvm.ptr,
      %public_output: !llvm.ptr {
        sps.fixture_refs = ["public-memory:public_output"],
        sps.sink_class = "public"}) {
    llvm.call @abi_alias_explicit_same_actual_helper(
        %secret, %shared, %shared, %public_output) {
          sps.fixture_refs = ["call:same-actual-p-q"],
          sps.site_alias = "same-actual-p-q"
        } : (i32, !llvm.ptr, !llvm.ptr, !llvm.ptr) -> ()
    llvm.return
  }
}
