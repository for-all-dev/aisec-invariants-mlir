// RUN: %checkpoint-runner run --snapshot fixtures/kyberslash1-poly-tomsg/target-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/kyberslash1-poly-tomsg/target-bad/kyberslash1_poly_tomsg.target_bad.mlir --records %t.checkpoints

// Synthetic target-control oracle.  This hand-authored model is not asserted
// to be compiler output; it makes an explicit target branch available to the
// SPS BranchSuccessor semantics while deployment evidence remains open.
module {
  llvm.func @kyberslash1_poly_tomsg_target_bad(
      %coefficient: i16 {
        sps.component_ref = "coefficient",
        sps.fixture_refs = ["snapshot.secret[0]"],
        sps.label = "high"}) -> i8 {
    %zero16 = llvm.mlir.constant(0 : i16) : i16
    %is_zero = llvm.icmp "eq" %coefficient, %zero16 : i16
    // PREFLIGHT FINDING: secret-dependent target branch
    // secret source: %is_zero is derived from secret %coefficient
    // observable effect: the observer-visible compute host exposes the immediate successor
    // reason: coefficients zero and one select different target blocks
    // preflight expectation: the target-control oracle selects BranchSuccessor.successor as first bad
    llvm.cond_br %is_zero, ^zero, ^nonzero {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["control"]
    }
  ^zero:
    %zero8 = llvm.mlir.constant(0 : i8) : i8
    llvm.return %zero8 : i8
  ^nonzero:
    %coefficient32 = llvm.zext %coefficient : i16 to i32
    %one = llvm.mlir.constant(1 : i32) : i32
    %round = llvm.mlir.constant(1664 : i32) : i32
    %q = llvm.mlir.constant(3329 : i32) : i32
    %shifted = llvm.shl %coefficient32, %one : i32
    %numerator = llvm.add %shifted, %round : i32
    %quotient = llvm.udiv %numerator, %q : i32
    %bit32 = llvm.and %quotient, %one : i32
    %bit8 = llvm.trunc %bit32 : i32 to i8
    llvm.return %bit8 : i8
  }
}
