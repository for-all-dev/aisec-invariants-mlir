// RUN: %checkpoint-runner run --snapshot fixtures/loop-bounds/public-bound-exhausted-unknown/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/loop-bounds/public-bound-exhausted-unknown/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/loop-bounds/public-bound-exhausted-unknown/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/loop-bounds/public-bound-exhausted-unknown/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/loop-bounds/public-bound-exhausted-unknown/bound_exhausted_loop.unknown.mlir --records %t.checkpoints

//
// scope note: with the configuration binding public bound set below public_count, both
// exact product lanes reach the same modeled BoundExhausted transition; bound adequacy stays
// open and no replayable bad execution is produced.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// Countermodel MT-CM2, which refutes the invalid principle "bounded-run
// filtering is a sound proof domain".
//
// The paired `bound_secret_trip_count.bad.mlir` covers the immediate structural
// counterexample. This fixture isolates the different question: two low-equal
// lanes follow the same public loop, but the configured proof bound is too small.
//
// THE UNSOUND SHORTCUT THIS PINS: an implementation that DELETES the execution
// exceeding its unrolling guard silently narrows the proof domain and reports a
// safe result. Rev-4 leaves the admitted execution in scope; bound adequacy fails
// because the public execution exceeds the guard, and the guarded expansion
// produces BoundExhausted instead of deleting the path. Execution-bound adequacy
// and universal definedness are deliberately NOT pair filters inside Admitted;
// they are universal proof obligations. Filtering an execution after it exhausts
// a bound, faults, fails, or risks undefined behavior is forbidden.
//
// WHY Unknown RATHER THAN Counterexample: a reachable, exactly modeled BoundExhausted
// transition that does not yield a replayed bad execution is Unknown with the
// bound-adequacy obligation open. Promoting it to a counterexample without a
// replayable witness is exactly what the spec forbids.
//
// REASON-CODE CONFLATION TO AVOID: loop-remainder denotes an exactly modeled
// reachable BoundExhausted transition. It must NEVER denote an insufficient
// engine cap, which is a separate resource-limit result. Collapsing the two into
// one identifier is the easiest wrong reduction here.
//
//
// The backedge must survive: a fixture whose loop is unrolled or deleted stops
// testing bound adequacy entirely.
module {
  llvm.func @bound_exhausted_public_loop(
      %public_count: i32 {sps.fixture_refs = ["snapshot.public[0]"], sps.label = "public", sps.bound_candidate = "public_trip_count_candidate"},
      %public_sink: !llvm.ptr {sps.sink_class = "public"}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i32) : i32
    llvm.br ^loop(%zero : i32)
  ^loop(%i: i32):
    %continue = llvm.icmp "slt" %i, %public_count : i32
    llvm.cond_br %continue, ^body, ^exit {
      sps.fixture_refs = ["snapshot.public[1]"],
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
