// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/different-successor-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/different-successor-bad/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/precision-control/different-successor-bad/precision_different_successor.bad.mlir --records %t.checkpoints

// Anti-control for identical-successor: output values remain equal, but the
// High condition selects distinct immediate successor identities.
module {
  llvm.func @different_successor_bad(
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
    llvm.cond_br %condition, ^secret_true, ^secret_false
        {sps.fixture_refs = ["observable:control"], sps.observable_candidate = ["control"]}
  ^secret_true:
    // The distinct documentary attributes keep canonicalization from
    // tail-merging away the immediate-successor anti-control.
    llvm.br ^merge {sps.site_alias = "true-path"}
  ^secret_false:
    llvm.br ^merge {sps.site_alias = "false-path"}
  ^merge:
    llvm.return %public_value : i32
  }
}
