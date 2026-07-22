// RUN: %mlir-opt %s | %FileCheck %s --implicit-check-not=llvm.cond_br --implicit-check-not=llvm.getelementptr
// RUN: %mlir-opt %s | %FileCheck %s --check-prefix=COUNT --implicit-check-not=llvm.cond_br --implicit-check-not=llvm.getelementptr
//
// case: secret-dependent embedding index
// classification: seeded-semantic-harness
// c source: ../c/secret_embedding_index_fixed.c
// upstream GitHub source: none -- conceptual tensor information-flow harness
// upstream revision: none
// secret: %secret_index
// public: table base, table contents, scan indices, and fixed table size 16
// expected outcome: verified
// observer/model: source-memory-address-trace
// reason id: secret-independent-address-scan
// outstanding obligations: none
// evidence boundary: L1 source address trace; preservation is checked separately at L3
//
// CHECK-LABEL: llvm.func @secret_embedding_index_fixed
// CHECK-SAME: %[[TABLE:[a-zA-Z0-9_]+]]: !llvm.ptr, %[[SECRET:[a-zA-Z0-9_]+]]: i32
// CHECK: %[[ZERO32:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[ZERO64:[0-9]+]] = llvm.mlir.constant(0 : i64) : i64
// CHECK: %[[ONE64:[0-9]+]] = llvm.mlir.constant(1 : i64) : i64
// CHECK: %[[BOUND:[0-9]+]] = llvm.mlir.constant(16 : i64) : i64
// CHECK: %[[MASK:[0-9]+]] = llvm.mlir.constant(15 : i32) : i32
// CHECK: %[[MASKED_SECRET:[0-9]+]] = llvm.and %[[SECRET]], %[[MASK]]
// CHECK-NOT: llvm.getelementptr
// CHECK: llvm.br ^bb1(%[[ZERO64]], %[[ZERO32]] : i64, i32)
// CHECK: ^bb1(%[[INDEX:[0-9]+]]: i64,
// CHECK: %[[IN_RANGE:[0-9]+]] = llvm.icmp "ult" %[[INDEX]], %[[BOUND]] : i64
// CHECK: llvm.cond_br %[[IN_RANGE]],
// CHECK-NOT: llvm.getelementptr
// CHECK: %[[SLOT:[0-9]+]] = llvm.getelementptr %[[TABLE]][%[[INDEX]]]
// CHECK: %[[VALUE:[0-9]+]] = llvm.load %[[SLOT]]
// CHECK: %[[NEXT_ACC:[0-9]+]] = llvm.or
// CHECK: %[[NEXT_INDEX:[0-9]+]] = llvm.add %[[INDEX]], %[[ONE64]]
// CHECK: llvm.br ^bb1(%[[NEXT_INDEX]], %[[NEXT_ACC]] : i64, i32)
// CHECK-NOT: llvm.getelementptr
// CHECK: llvm.return
//
// COUNT-COUNT-1: llvm.cond_br
// COUNT-COUNT-1: llvm.getelementptr
module {
  llvm.func @secret_embedding_index_fixed(
      %table: !llvm.ptr, %secret_index: i32) -> i32 {
    %zero32 = llvm.mlir.constant(0 : i32) : i32
    %zero64 = llvm.mlir.constant(0 : i64) : i64
    %one64 = llvm.mlir.constant(1 : i64) : i64
    %sixteen = llvm.mlir.constant(16 : i64) : i64
    %fifteen = llvm.mlir.constant(15 : i32) : i32
    %selected_index = llvm.and %secret_index, %fifteen : i32
    llvm.br ^scan(%zero64, %zero32 : i64, i32)
  ^scan(%i: i64, %acc: i32):
    %continue = llvm.icmp "ult" %i, %sixteen : i64
    llvm.cond_br %continue, ^body, ^done(%acc : i32)
  ^body:
    %slot = llvm.getelementptr %table[%i] : (!llvm.ptr, i64) -> !llvm.ptr, i32
    // CONFIDENTIALITY REPAIR: scan a public induction address
    // secret source: %selected_index affects only the data mask, not %slot
    // removed observable: every run loads all 16 table addresses in the same order
    // reason: %i is a public fixed-bound induction variable
    // detection boundary: direct L1 memory-address effect passes at this boundary
    %value = llvm.load %slot : !llvm.ptr -> i32
    %i32 = llvm.trunc %i : i64 to i32
    %equal = llvm.icmp "eq" %i32, %selected_index : i32
    %equal32 = llvm.zext %equal : i1 to i32
    %mask = llvm.sub %zero32, %equal32 : i32
    %candidate = llvm.and %value, %mask : i32
    %next_acc = llvm.or %acc, %candidate : i32
    %next_i = llvm.add %i, %one64 : i64
    llvm.br ^scan(%next_i, %next_acc : i64, i32)
  ^done(%result: i32):
    llvm.return %result : i32
  }
}
