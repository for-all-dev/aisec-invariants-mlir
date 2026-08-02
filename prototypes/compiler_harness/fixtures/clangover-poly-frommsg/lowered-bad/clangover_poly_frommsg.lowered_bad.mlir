// RUN: %checkpoint-runner run --snapshot fixtures/clangover-poly-frommsg/lowered-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/clangover-poly-frommsg/lowered-bad/clangover_poly_frommsg.lowered_bad.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic target check; exact product bit witness; backend evidence
// artifact status: hand-written target model derived from verified assembly
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  // Verified x86 excerpt from the reduction:
  //   btl %ecx, %r8d
  //   jae .LBB0_4
  llvm.func @clangover_poly_frommsg_x86_bad_model(
      %bit: i1 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i16 {
    %zero = llvm.mlir.constant(0 : i16) : i16
    %constant = llvm.mlir.constant(1665 : i16) : i16
    // PREFLIGHT FINDING: secret-dependent branch
    // secret source: %bit is derived from the secret message
    // observable effect: branch direction and execution timing
    // reason: inputs differing only in %bit select different successors
    // preflight expectation: unary scanner flags the candidate-secret branch in this target model
    llvm.cond_br %bit, ^taken, ^not_taken {
      sps.fixture_refs = ["snapshot.public[0]", "snapshot.public[1]"],
      sps.observable_candidate = ["control", "timing"]
    }
  ^taken:
    llvm.return %constant : i16
  ^not_taken:
    llvm.return %zero : i16
  }
}
