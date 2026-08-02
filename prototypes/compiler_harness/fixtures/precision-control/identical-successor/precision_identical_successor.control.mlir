// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/identical-successor/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/identical-successor/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/precision-control/identical-successor/precision_identical_successor.control.mlir --records %t.checkpoints

// Relational precision control: the High condition is used, but both edges
// name the same immediate successor and the public return is unchanged.
// sps.* attributes are review locators only; policy/ABI sidecars own binding.
// The C file is functional provenance. Clang -O0 need not preserve this
// deliberately hand-authored identical-successor trace.
module {
  llvm.func @identical_successor_control(
      %high_condition: i32 {
        sps.component_ref = "high-condition",
        sps.fixture_refs = ["secret:high_condition"],
        sps.label = "high"},
      %public_value: i32 {
        sps.component_ref = "public-value",
        sps.fixture_refs = ["public:public_value"],
        sps.label = "public"}) -> i32 {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %condition = llvm.icmp "ne" %high_condition, %zero : i32
    llvm.cond_br %condition, ^merge, ^merge
        {sps.fixture_refs = ["observable:control"], sps.observable_candidate = ["control"]}
  ^merge:
    llvm.return %public_value : i32
  }
}
