// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: secret-dependent embedding index
// classification: seeded-semantic-harness
// c source: ../c/secret_embedding_index_bad.c
// upstream GitHub source: none -- conceptual tensor information-flow harness
// upstream revision: none
// secret: %secret_index
// public: table base, table contents, and fixed table size 16
// expected outcome: unsafe
// observer/model: source-memory-address-trace
// reason id: secret-dependent-address
// outstanding obligations: none
// evidence boundary: direct L1 address-effect check; no torch-mlir defect is claimed
//
// CHECK-LABEL: llvm.func @secret_embedding_index_bad
// CHECK-SAME: %[[TABLE:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[SECRET:[a-zA-Z0-9_]+]]: i32
// CHECK: %[[MASK:[0-9]+]] = llvm.mlir.constant(15 : i32) : i32
// CHECK: %[[MASKED:[0-9]+]] = llvm.and %[[SECRET]], %[[MASK]]
// CHECK: %[[INDEX:[0-9]+]] = llvm.zext %[[MASKED]] : i32 to i64
// CHECK: %[[SLOT:[0-9]+]] = llvm.getelementptr %[[TABLE]][%[[INDEX]]]
// CHECK: llvm.load %[[SLOT]]
module {
  llvm.func @secret_embedding_index_bad(
      %table: !llvm.ptr, %secret_index: i32) -> i32 {
    %fifteen = llvm.mlir.constant(15 : i32) : i32
    %masked = llvm.and %secret_index, %fifteen : i32
    %index = llvm.zext %masked : i32 to i64
    %slot = llvm.getelementptr %table[%index] : (!llvm.ptr, i64) -> !llvm.ptr, i32
    // CONFIDENTIALITY ERROR: secret-dependent embedding address
    // secret source: %slot is computed from %secret_index
    // observable effect: the cache-line or memory-address trace identifies the selected row
    // reason: equal public tables produce different load addresses for different secret indices
    // detection boundary: direct L1 memory-address effect; L2 may return an index pair
    // expected-error @+1 {{secret-dependent-address}}
    %value = llvm.load %slot : !llvm.ptr -> i32
    llvm.return %value : i32
  }
}
