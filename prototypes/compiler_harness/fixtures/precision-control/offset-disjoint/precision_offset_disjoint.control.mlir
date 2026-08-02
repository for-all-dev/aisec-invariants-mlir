// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/offset-disjoint/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/precision-control/offset-disjoint/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner finalize --test fixtures/precision-control/offset-disjoint/precision_offset_disjoint.control.mlir --records %t.checkpoints

// Relational precision control: exact allocation identity plus byte offset
// separates the High byte at 4 from the Low byte loaded at 8. Coarsening both
// accesses to one allocation cannot establish this result.
module {
  llvm.func @offset_disjoint_control(
      %buffer: !llvm.ptr {
        sps.abi_root_ref = "buffer",
        sps.fixture_refs = ["public:buffer"],
        sps.label = "public"},
      %secret_byte: i32 {
        sps.component_ref = "secret-byte",
        sps.fixture_refs = ["secret:secret_byte"],
        sps.label = "high"},
      %public_value: i32 {
        sps.component_ref = "public-value",
        sps.fixture_refs = ["public:public_value"],
        sps.label = "public"}) -> i32 {
    %off_secret = llvm.mlir.constant(4 : i32) : i32
    %off_public = llvm.mlir.constant(8 : i32) : i32
    %secret_slot = llvm.getelementptr %buffer[%off_secret] : (!llvm.ptr, i32) -> !llvm.ptr, i8
    %public_slot = llvm.getelementptr %buffer[%off_public] : (!llvm.ptr, i32) -> !llvm.ptr, i8
    %secret_i8 = llvm.trunc %secret_byte : i32 to i8
    %public_i8 = llvm.trunc %public_value : i32 to i8
    llvm.store %secret_i8, %secret_slot {sps.label = "high"} : i8, !llvm.ptr
    llvm.store %public_i8, %public_slot {sps.label = "public"} : i8, !llvm.ptr
    %reloaded_i8 = llvm.load %public_slot : !llvm.ptr -> i8
    %result = llvm.zext %reloaded_i8 : i8 to i32
    llvm.return %result : i32
  }
}
