// RUN: %checkpoint-runner run --snapshot fixtures/loop-bounds/secret-trip-count-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/loop-bounds/secret-trip-count-bad/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/loop-bounds/secret-trip-count-bad/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/loop-bounds/secret-trip-count-bad/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/loop-bounds/secret-trip-count-bad/bound_secret_trip_count.bad.mlir --records %t.checkpoints

//
// scope note: exact product replays secret counts 0 and 1; the first conditional
// branch chooses exit in one lane and body in the other before any bound exhausts.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// This is deliberately separate from bound_exhausted_loop.unknown.mlir. A secret
// trip count is already a replayable structural counterexample; it cannot be
// relabeled Unknown merely because a later execution might exceed a proof bound.
//
module {
  llvm.func @bound_secret_trip_count_bad(
      %secret_count: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i32) : i32
    llvm.br ^loop(%zero : i32)
  ^loop(%i: i32):
    %continue = llvm.icmp "slt" %i, %secret_count : i32
    // PREFLIGHT FINDING: secret changes loop-continuation control
    // secret source: %secret_count differs between the two admitted lanes
    // observable effect: the first branch chooses body for count 1 and exit for count 0
    // reason: world-level control locations must remain in lockstep while active
    // preflight expectation: unary scanner flags the candidate-secret loop condition
    llvm.cond_br %continue, ^body, ^exit {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["control"]
    }
  ^body:
    %next = llvm.add %i, %one : i32
    llvm.br ^loop(%next : i32)
  ^exit:
    llvm.store %zero, %public_sink {sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
