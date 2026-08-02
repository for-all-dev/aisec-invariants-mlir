// RUN: %checkpoint-runner run --snapshot fixtures/pointer-rebinding/same-allocation-control/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner run --snapshot fixtures/pointer-rebinding/same-allocation-control/snapshot.yaml --pipeline canonicalized-shape --endpoint %t.canonicalized.mlir --records %t.checkpoints -- %mlir-opt %s --canonicalize -o %t.canonicalized.mlir
// RUN: %checkpoint-runner check-existing --snapshot fixtures/pointer-rebinding/same-allocation-control/snapshot.yaml --pipeline candidate-bitcode --endpoint fixtures/pointer-rebinding/same-allocation-control/candidate/artifact.bc --records %t.checkpoints
// RUN: %checkpoint-runner finalize --test fixtures/pointer-rebinding/same-allocation-control/pointer_rebinding_same_allocation.control.mlir --records %t.checkpoints

// This is the precision twin of disjoint-select-bad. The frozen instructions
// are identical, but the ABI puts left and right in one allocation class, so
// the selected Memory allocationClass is equal in both lanes.
module {
  llvm.func @pointer_rebinding_same_allocation_control(
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
    %selected_right = llvm.icmp "ne" %secret_selector, %zero : i32
    %selected = llvm.select %selected_right, %right, %left : i1, !llvm.ptr
    %value = llvm.load %selected : !llvm.ptr -> i8
    llvm.store %value, %private_result : i8, !llvm.ptr
    llvm.return
  }
}
