// case: secret-dependent embedding index
// classification: seeded-semantic-harness
// c source: ../c/secret_embedding_index_fixed.c
// upstream GitHub source: none -- conceptual tensor information-flow harness
// upstream revision: none
// secret: %secret_index
// public: table base, table contents, scan indices, and fixed table size 16
// expected verdict: pass at this source boundary; later lowering must preserve the fixed scan
// exact incident boundary: L1 address-effect check; L3 checks preservation after lowering
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
