// RUN: %checkpoint-runner run --snapshot fixtures/kyberslash1-poly-tomsg/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/kyberslash1-poly-tomsg/bad/kyberslash1_poly_tomsg.bad.mlir --records %t.checkpoints

//
// scope note: direct preflight diagnostic variable-time division check
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @kyberslash1_poly_tomsg_bad(
      %coefficient: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %round = llvm.mlir.constant(1664 : i32) : i32
    %q = llvm.mlir.constant(3329 : i32) : i32
    %shifted = llvm.shl %coefficient, %one : i32
    %numerator = llvm.add %shifted, %round : i32
    // PREFLIGHT FINDING: secret-dependent division
    // secret source: %numerator is derived from secret %coefficient
    // observable effect: division latency can vary with the numerator value
    // reason: inputs differing only in %coefficient execute a variable-time llvm.udiv
    // preflight expectation: direct preflight diagnostic source/LLVM-dialect check
    %quotient = llvm.udiv %numerator, %q {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["timing"]
    } : i32
    %bit = llvm.and %quotient, %one : i32
    llvm.return %bit : i32
  }
}
