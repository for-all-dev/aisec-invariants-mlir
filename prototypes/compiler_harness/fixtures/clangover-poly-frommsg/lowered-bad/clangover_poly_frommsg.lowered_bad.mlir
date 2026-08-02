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
      %out: !llvm.ptr {sps.abi_root_ref = "out", sps.output_ref = "out"},
      %msg: !llvm.ptr {
        sps.abi_root_ref = "msg",
        sps.fixture_refs = ["snapshot.secret[0]"],
        sps.label = "high"}) {
    %message_byte = llvm.load %msg : !llvm.ptr -> i8
    %one8 = llvm.mlir.constant(1 : i8) : i8
    %bit = llvm.and %message_byte, %one8 : i8
    %zero8 = llvm.mlir.constant(0 : i8) : i8
    %is_one = llvm.icmp "ne" %bit, %zero8 : i8
    %zero16 = llvm.mlir.constant(0 : i16) : i16
    %constant16 = llvm.mlir.constant(1665 : i16) : i16
    // PREFLIGHT FINDING: secret-dependent branch
    // secret source: %is_one is derived from the byte loaded through secret root %msg
    // observable effect: the observer-visible compute host exposes the immediate successor
    // reason: messages beginning with 0x00 and 0x01 select different target blocks
    // preflight expectation: the target-control oracle selects BranchSuccessor.successor as first bad
    llvm.cond_br %is_one, ^taken, ^not_taken {
      sps.fixture_refs = ["snapshot.public[0]"],
      sps.observable_candidate = ["control"]
    }
  ^taken:
    llvm.store %constant16, %out : i16, !llvm.ptr
    llvm.return
  ^not_taken:
    llvm.store %zero16, %out : i16, !llvm.ptr
    llvm.return
  }
}
