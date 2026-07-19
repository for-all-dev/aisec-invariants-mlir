// case: secret-dependent embedding index
// classification: seeded-semantic-harness
// c source: ../c/secret_embedding_index_bad.c
// upstream GitHub source: none -- conceptual tensor information-flow harness
// upstream revision: none
// secret: %secret_index
// public: table base, table contents, and fixed table size 16
// expected verdict: reject
// exact incident boundary: direct L1 address-effect check; no torch-mlir defect is claimed
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
    %value = llvm.load %slot : !llvm.ptr -> i32
    llvm.return %value : i32
  }
}
