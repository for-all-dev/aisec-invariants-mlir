// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/identical-successor/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/identical-successor/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/precision-control/identical-successor/precision_identical_successor.control.mlir --records %t.checkpoints

//
// scope note: the unary scanner flags a relational review site; a future
// Section-10 diagnostic must defer the proof question to the exact product.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// This is a NEGATIVE CONTROL. It is release-relative noninterferent: the secret
// condition selects between two edges that target one block, so no
// coalition-visible control location differs. Section 11 disjunct 2 ("next
// control locations differ") cannot fire when the successor set is a singleton.
//
// A future SPS analysis that reports a violation here is imprecise, not
// correct. The imprecision MUST NOT be repaired by the rule "identical
// successors imply no control leak": the paired anti-control
// fixtures/predecessor-choice/blockarg-bad/predecessor_choice_blockarg.bad.mlir
// canonicalizes to this same successor shape and differs only in its
// block-argument operands. Nor may it be repaired
// by treating a diagnostic disposition as proof-authoritative.
//
//
// The second RUN pins that the shape is stable under canonicalization, so the
// control cannot silently decay into a different scenario.
module {
  llvm.func @identical_successor_control(
      %high_condition: i1 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %public_sink: !llvm.ptr {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"}) {
    %public_value = llvm.mlir.constant(7 : i32) : i32
    llvm.cond_br %high_condition, ^merge, ^merge
        {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["control"]}
  ^merge:
    llvm.store %public_value, %public_sink
        {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
