// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/xor-secret-output-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/xor-secret-output-bad/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/precision-control/xor-secret-output-bad/precision_xor_secret_output.bad.mlir --records %t.checkpoints

// Anti-control for XOR cancellation: the second operand is public zero, so the
// returned value varies with the High input.
module {
  llvm.func @xor_secret_output_bad(
      %secret: i32 {
        sps.component_ref = "secret",
        sps.fixture_refs = ["secret:secret"],
        sps.label = "high"}) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %leaked = llvm.xor %secret, %zero : i32
    llvm.return %leaked : i32
  }
}
