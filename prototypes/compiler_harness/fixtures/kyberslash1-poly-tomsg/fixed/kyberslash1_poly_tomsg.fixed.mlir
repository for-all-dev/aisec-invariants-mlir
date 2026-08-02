// RUN: %checkpoint-runner run --snapshot fixtures/kyberslash1-poly-tomsg/fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/kyberslash1-poly-tomsg/fixed/kyberslash1_poly_tomsg.fixed.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic source-operation model confirms no division remains
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @kyberslash1_poly_tomsg_fixed(
      %coefficient: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %round = llvm.mlir.constant(1665 : i32) : i32
    %reciprocal = llvm.mlir.constant(80635 : i32) : i32
    %shift = llvm.mlir.constant(28 : i32) : i32
    %shifted = llvm.shl %coefficient, %one : i32
    %numerator = llvm.add %shifted, %round : i32
    // PREFLIGHT CONTROL: reciprocal multiply replaces division
    // secret source: %numerator is derived from secret %coefficient
    // safe effect: no division instruction or helper is selected
    // reason: multiply/add/shift sequence preserves the documented bit result on the Kyber coefficient domain
    // preflight expectation: preflight diagnostic confirms forbidden division is absent
    %scaled = llvm.mul %numerator, %reciprocal {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["timing"]
    } : i32
    %quotient = llvm.lshr %scaled, %shift : i32
    %bit = llvm.and %quotient, %one : i32
    llvm.return %bit : i32
  }
}
