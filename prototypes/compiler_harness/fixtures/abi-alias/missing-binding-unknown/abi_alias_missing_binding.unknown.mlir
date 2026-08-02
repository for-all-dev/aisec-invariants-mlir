// RUN: %checkpoint-runner run --snapshot fixtures/abi-alias/missing-binding-unknown/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/abi-alias/missing-binding-unknown/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/abi-alias/missing-binding-unknown/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/abi-alias/missing-binding-unknown/abi_alias_missing_binding.unknown.mlir --records %t.checkpoints

//
// scope note: configuration binding supplies no proved separation clause for %p and %q, so
// preflight diagnostic cannot close the store-to-load edge and no exact product conclusion follows.
//
// Countermodel MT-CM5, which refutes the invalid principle "unproved ABI alias
// separation may be assumed".
//
// The secret is stored through %p and a value is reloaded through %q, then sent
// to a public output. The ABI sidecar intentionally omits the complete alias
// topology, so neither overlapping nor disjoint calls are admitted precisely.
//
// Merely naming two buffers differently establishes neither choice.
// PublicAliasTopology is a conjunct of LowEq^0, and EntryABIConforms must
// include the COMPLETE alias relation.
//
// WHY THIS IS unknown: a replay needs a complete ABI relation. The paired
// abi_alias_mayalias_overlap.bad fixture admits p==q and yields a counterexample;
// abi_alias_disjoint.control admits only disjoint roots and is the positive twin.
//
// DELIBERATE TRAP: distinct !llvm.ptr arguments and distinct SSA names establish
// no separation. There is intentionally no alias attribute here; policy must be
// supplied by the independent ABI sidecar and bound to frozen bitcode.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @abi_alias_missing_binding(
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
    llvm.store %reloaded, %public_output {
      sps.fixture_refs = ["store:q-to-public-output"],
      sps.sink_class = "public",
      sps.site_alias = "q-to-public-output"
    } : i32, !llvm.ptr
    llvm.return
  }
}
