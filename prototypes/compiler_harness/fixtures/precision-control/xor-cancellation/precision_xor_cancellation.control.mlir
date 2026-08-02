// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/xor-cancellation/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/xor-cancellation/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/precision-control/xor-cancellation/precision_xor_cancellation.control.mlir --records %t.checkpoints

// Relational precision control: unary dependence marks this expression High,
// while extensional two-run reasoning establishes secret xor secret == 0.
module {
  llvm.func @xor_cancellation_control(
      %secret: i32 {
        sps.component_ref = "secret",
        sps.fixture_refs = ["secret:secret"],
        sps.label = "high"}) -> i32 {
    %cancelled = llvm.xor %secret, %secret : i32
    llvm.return %cancelled : i32
  }
}
