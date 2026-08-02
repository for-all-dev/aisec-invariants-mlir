// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/overwritten-slot/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/overwritten-slot/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/precision-control/overwritten-slot/precision_overwritten_slot.control.mlir --records %t.checkpoints

// Relational precision control: the High store is killed by a complete Low
// overwrite before the only load and public return. The constant alloca size is
// part of the case; a secret-dependent allocation is a different obligation.
module {
  llvm.func @overwritten_slot_control(
      %secret: i32 {
        sps.component_ref = "secret",
        sps.fixture_refs = ["secret:secret"],
        sps.label = "high"},
      %public_value: i32 {
        sps.component_ref = "public-value",
        sps.fixture_refs = ["public:public_value"],
        sps.label = "public"}) -> i32 {
    %one = llvm.mlir.constant(1 : i64) : i64
    %slot = llvm.alloca %one x i32 {sps.site_alias = "alloca.slot"} : (i64) -> !llvm.ptr
    llvm.store %secret, %slot {sps.label = "high"} : i32, !llvm.ptr
    llvm.store %public_value, %slot {sps.label = "public"} : i32, !llvm.ptr
    %reloaded = llvm.load %slot : !llvm.ptr -> i32
    llvm.return %reloaded : i32
  }
}
