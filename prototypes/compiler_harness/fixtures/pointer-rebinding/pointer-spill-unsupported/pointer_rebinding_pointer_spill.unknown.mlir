// RUN: %checkpoint-runner run --snapshot fixtures/pointer-rebinding/pointer-spill-unsupported/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/pointer-rebinding/pointer-spill-unsupported/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/pointer-rebinding/pointer-spill-unsupported/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/pointer-rebinding/pointer-spill-unsupported/pointer_rebinding_pointer_spill.unknown.mlir --records %t.checkpoints

// Pointer selection itself is supported, but this frozen shape serializes the
// structural pointer through ordinary memory. Rev4.1 rejects the pointer-valued
// store/load with Unknown(UnsupportedType) before relational construction.
module {
  llvm.func @pointer_rebinding_pointer_spill_unsupported(
      %secret_selector: i32 {
        sps.component_ref = "secret-selector",
        sps.fixture_refs = ["secret:secret_selector"],
        sps.label = "high"},
      %left: !llvm.ptr {sps.abi_root_ref = "left"},
      %right: !llvm.ptr {sps.abi_root_ref = "right"},
      %private_result: !llvm.ptr {
        sps.abi_root_ref = "private-result",
        sps.fixture_refs = ["private-memory:private_result"],
        sps.output_ref = "private-result",
        sps.sink_class = "private"}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %one = llvm.mlir.constant(1 : i64) : i64
    %selected_right = llvm.icmp "ne" %secret_selector, %zero : i32
    %selected = llvm.select %selected_right, %right, %left : i1, !llvm.ptr
    %slot = llvm.alloca %one x !llvm.ptr : (i64) -> !llvm.ptr
    llvm.store %selected, %slot : !llvm.ptr, !llvm.ptr
    %reloaded = llvm.load %slot : !llvm.ptr -> !llvm.ptr
    %value = llvm.load %reloaded : !llvm.ptr -> i8
    llvm.store %value, %private_result : i8, !llvm.ptr
    llvm.return
  }
}
