// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: direct preflight diagnostic address-effect check; no torch-mlir defect is claimed
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @secret_embedding_index_bad
// CHECK-SAME: %[[TABLE:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[SECRET:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}
// CHECK: %[[MASK:[0-9]+]] = llvm.mlir.constant(15 : i32) : i32
// CHECK: %[[MASKED:[0-9]+]] = llvm.and %[[SECRET]], %[[MASK]]
// CHECK: %[[INDEX:[0-9]+]] = llvm.zext %[[MASKED]] : i32 to i64
// CHECK: %[[SLOT:[0-9]+]] = llvm.getelementptr %[[TABLE]][%[[INDEX]]] {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["address"]}
// CHECK: llvm.load %[[SLOT]]
module {
  llvm.func @secret_embedding_index_bad(
      %table: !llvm.ptr,
      %secret_index: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i32 {
    %fifteen = llvm.mlir.constant(15 : i32) : i32
    %masked = llvm.and %secret_index, %fifteen : i32
    %index = llvm.zext %masked : i32 to i64
    %slot = llvm.getelementptr %table[%index] {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["address"]
    } : (!llvm.ptr, i64) -> !llvm.ptr, i32
    // PREFLIGHT FINDING: secret-dependent embedding address
    // secret source: %slot is computed from %secret_index
    // observable effect: the cache-line or memory-address trace identifies the selected row
    // reason: equal public tables produce different load addresses for different secret indices
    // preflight expectation: unary scanner flags the candidate-secret address computation
    %value = llvm.load %slot : !llvm.ptr -> i32
    llvm.return %value : i32
  }
}
