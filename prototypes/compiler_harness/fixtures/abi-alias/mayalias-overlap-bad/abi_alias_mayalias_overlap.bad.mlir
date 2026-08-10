// RUN: %checkpoint-runner run --snapshot fixtures/abi-alias/mayalias-overlap-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/abi-alias/mayalias-overlap-bad/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/abi-alias/mayalias-overlap-bad/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/abi-alias/mayalias-overlap-bad/abi_alias_mayalias_overlap.bad.mlir --records %t.checkpoints

//
// scope note: the independent ABI sidecar fixes p and q as zero-offset views
// of one allocation; two secret values therefore yield two public outputs.
//
// The sps.abi_root_ref attributes are documentary root locators only. The checked
// ABI sidecar, not the IR, authorizes the overlapping realization.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
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
    // observable effect: the q reload receives the secret stored through p
    // reason: the fixed same-allocation ABI topology gives p and q one allocation key
    // preflight expectation: preserve the store/load/public-sink shape for later ABI binding
    llvm.store %reloaded, %public_output {
      sps.fixture_refs = ["store:q-to-public-output"],
      sps.sink_class = "public",
      sps.site_alias = "q-to-public-output"
    } : i32, !llvm.ptr
    llvm.return
  }
}
