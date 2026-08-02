// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/overwritten-slot/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/overwritten-slot/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/precision-control/overwritten-slot/precision_overwritten_slot.control.mlir --records %t.checkpoints

//
// scope note: the unary scanner flags a relational review site at the reload;
// the eventual exact product decides whether the reloaded words are equal.
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// This is a NEGATIVE CONTROL. The secret is stored into a stack slot and then
// fully overwritten by a public value before any load, so the reloaded word is
// identical in both lanes.
//
// Only a strong update discharges this statically, and SPS Rev-4 section 10
// states the diagnostic analysis has "no proof-authoritative strong update, no
// summaries, and no slice selection". This preflight therefore records only a
// relational candidate; the kill/gen reasoning belongs in the exact product.
// An implementation that adds a proof-authoritative strong update to the
// diagnostic layer to make this fixture quiet has become unsound; that is the
// specific regression this control guards.
//
// Measured with mlir-opt 17.0.6: --canonicalize does NOT eliminate either store
// to the slot, so the overwrite shape survives and the control stays meaningful.
//
//
module {
  llvm.func @overwritten_slot_control(
      %secret: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %public_count: i32 {sps.label = "public"},
      %public_value: i32 {sps.label = "public"},
      %public_sink: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"}) {
    %slot = llvm.alloca %public_count x i32 : (i32) -> !llvm.ptr
    llvm.store %secret, %slot {sps.label = "high"} : i32, !llvm.ptr
    llvm.store %public_value, %slot {sps.label = "public"} : i32, !llvm.ptr
    %reloaded = llvm.load %slot : !llvm.ptr -> i32
    llvm.store %reloaded, %public_sink
        {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
