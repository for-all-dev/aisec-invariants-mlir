// RUN: %checkpoint-runner run --snapshot fixtures/loop-bounds/public-bound-adequate-proved/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/loop-bounds/public-bound-adequate-proved/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/loop-bounds/public-bound-adequate-proved/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/loop-bounds/public-bound-adequate-proved/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/loop-bounds/public-bound-adequate-proved/bound_adequate_loop.proved.mlir --records %t.checkpoints

//
// scope note: with the configuration binding public bound set at or above the
// admitted public_count, no admitted execution reaches the retained remainder;
// bound adequacy is discharged and both low-equal lanes agree on every loop
// decision and on the single public output.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// THE POSITIVE SIBLING OF `bound_exhausted_loop.unknown.mlir`. The two cases are
// the same program, the same policy, and the same admitted domain
// (`public_count == 8`). They differ in exactly one configuration field:
//
//     public-bound-exhausted-unknown   backedge_limit = 4   ->  Unknown(LoopRemainder)
//     public-bound-adequate-proved     backedge_limit = 8   ->  Proved
//
// That is the point of the pair. `BoundAdequate_e(T,B)` is a property of the
// program AND its declared bound, never of the program alone, so nothing about
// the C body or the policy can decide it on its own. A reader who believes
// "the loop is public and terminates, therefore Proved" is reading a property
// of T and ignoring B; these two fixtures differ only in B.
//
// WHY Proved RATHER THAN Unknown: the loop block executes exactly 8 times for
// the admitted count, the declared bound admits 8 copies, so the guarded
// expansion never reaches the retained remainder node. BoundExhausted is
// therefore unreachable rather than merely unobserved, which is what
// `BoundAdequate_e(T,B)` requires. The complementary boundary guard is asserted
// unreachable; it is never assumed false.
//
// WHAT THIS FIXTURE MUST NOT BECOME: if a future edit lowers the admitted count
// or raises it above the bound, this case silently turns into its sibling and
// stops testing discharge. If an edit deletes the backedge, it stops testing
// bound adequacy altogether. The off-by-one is deliberate and load-bearing:
// bound 8 with count 8 is exactly adequate, and bound 7 would not be.
//
// NOT A CERTIFICATE: adequacy here is discharged by ordinary guarded expansion
// within the declared bound, not by an inductive loop certificate. Rev4.1 has
// no certificate artifact; see roadmap RR-12.
//
// The backedge must survive: a fixture whose loop is unrolled or deleted stops
// testing bound adequacy entirely.
module {
  llvm.func @bound_adequate_public_loop(
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
