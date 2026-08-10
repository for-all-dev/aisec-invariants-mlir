// RUN: %checkpoint-runner run --snapshot fixtures/launder-scan/folded-mask-p4-open/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/launder-scan/folded-mask-p4-open/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/launder-scan/folded-mask-p4-open/launder_scan_folded_bad.p4_open.mlir --records %t.checkpoints

//
// C evidence: launder_scan_folded_bad.c
// modeled boundary: optimized LLVM before instruction selection
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// The C source is written as an arithmetic mask. InstCombine recognizes that
// blend and folds it back into the same branchless select produced for the
// ternary source. On x86, the backend can then convert this select-with-memory
// shape into a secret-dependent branch and conditional load. This fixture
// records the distinct source provenance even though its optimized LLVM shape
// matches the existing model-clean-p4-open case.
//
// This is a target-risk preflight fixture. It computes neither ModelStatus nor
// DeploymentStatus; the emitted-machine checks live under p4-risk/.
//
//
module {
  llvm.func @launder_scan_folded_bad(
      %secret: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %fallback: i64 {sps.label = "public"},
      %buffer: !llvm.ptr {sps.abi_root_ref = "buffer", sps.label = "public"},
      %owner_private_sink: !llvm.ptr {sps.abi_root_ref = "owner-private-sink", sps.output_ref = "owner-private-result", sps.sink_class = "private"}) {
    %loaded = llvm.load %buffer : !llvm.ptr -> i64
    %zero = llvm.mlir.constant(0 : i32) : i32
    %is_zero = llvm.icmp "eq" %secret, %zero : i32
    %blended = llvm.select %is_zero, %fallback, %loaded {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]", "snapshot.public[2]"],
      sps.observable_candidate = ["control", "address", "timing"]
    } : i1, i64
    llvm.store %blended, %owner_private_sink {
      sps.output_ref = "owner-private-result",
      sps.sink_class = "private"
    } : i64, !llvm.ptr
    llvm.return
  }
}
