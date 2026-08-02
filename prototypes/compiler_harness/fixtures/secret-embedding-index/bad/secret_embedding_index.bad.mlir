// RUN: %checkpoint-runner run --snapshot fixtures/secret-embedding-index/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/secret-embedding-index/bad/secret_embedding_index.bad.mlir --records %t.checkpoints

//
// scope note: direct preflight diagnostic address-effect check; no torch-mlir defect is claimed
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
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
