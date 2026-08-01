// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: the independent ABI sidecar admits p==q; exact product replays that
// realization and two secret values yield two public output values.
//
// The sps.abi_root_ref attributes are documentary root locators only. The checked
// ABI sidecar, not the IR, authorizes the overlapping realization.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @abi_alias_mayalias_overlap
// CHECK-SAME: {{.*}}sps.component_ref = "secret"
// CHECK-SAME: sps.fixture_refs = ["secret:secret"]
// CHECK-SAME: sps.label = "high"
// CHECK-SAME: {{.*}}sps.abi_root_ref = "p"
// CHECK-SAME: {{.*}}sps.abi_root_ref = "q"
// CHECK-SAME: {{.*}}sps.abi_root_ref = "public-output"
// CHECK-SAME: sps.fixture_refs = ["public-memory:public_output"]
// CHECK: llvm.store %{{.*}}, %[[P:.*]] {sps.fixture_refs = ["store:secret-through-p"], sps.label = "high", sps.site_alias = "secret-through-p"}
// CHECK: %[[V:[0-9]+]] = llvm.load %[[Q:.*]] :
// CHECK: llvm.store %[[V]], %{{.*}} {sps.fixture_refs = ["store:q-to-public-output"], sps.sink_class = "public", sps.site_alias = "q-to-public-output"}
module {
  llvm.func @abi_alias_mayalias_overlap(
      %secret: i32 {
        sps.component_ref = "secret",
        sps.fixture_refs = ["secret:secret"],
        sps.label = "high"},
      %p: !llvm.ptr {sps.abi_root_ref = "p"},
      %q: !llvm.ptr {sps.abi_root_ref = "q"},
      %public_output: !llvm.ptr {
        sps.abi_root_ref = "public-output",
        sps.fixture_refs = ["public-memory:public_output"],
        sps.sink_class = "public"}) {
    llvm.store %secret, %p {
      sps.fixture_refs = ["store:secret-through-p"],
      sps.label = "high",
      sps.site_alias = "secret-through-p"
    } : i32, !llvm.ptr
    %reloaded = llvm.load %q : !llvm.ptr -> i32
    // PREFLIGHT FINDING: admitted overlapping roots expose the secret
    // secret source: %secret is stored through p
    // observable effect: when p equals q, public_output receives the secret
    // reason: MayAlias requires the overlapping realization to remain in the product
    // preflight expectation: preserve the store/load/public-sink shape for later ABI binding
    llvm.store %reloaded, %public_output {
      sps.fixture_refs = ["store:q-to-public-output"],
      sps.sink_class = "public",
      sps.site_alias = "q-to-public-output"
    } : i32, !llvm.ptr
    llvm.return
  }
}
