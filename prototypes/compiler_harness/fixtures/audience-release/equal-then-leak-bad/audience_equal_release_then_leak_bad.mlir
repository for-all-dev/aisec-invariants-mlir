// RUN: %checkpoint-runner run --snapshot fixtures/audience-release/equal-then-leak-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/audience-release/equal-then-leak-bad/audience_equal_release_then_leak_bad.mlir --records %t.checkpoints

// The authorized release is equal in both lanes. EqualAuthorized records the
// event but does not retire the obligation, so the later transfer is still Bad.
module {
  llvm.func @llvm.sps.release(i32)
  llvm.func @sps_transfer_equal_release_observer(i32)

  llvm.func @audience_equal_release_then_leak_bad(
      %secret: i32 {sps.component_ref = "secret", sps.label = "high"}) {
    %zero = llvm.mlir.constant(0 : i32) : i32
    llvm.call @llvm.sps.release(%zero) {
      sps.release_ref = "zero-release",
      sps.site_alias = "zero-release"
    } : (i32) -> ()
    // PREFLIGHT FINDING: equal authorized release followed by secret transfer
    // secret source: %secret remains an outstanding relational obligation
    // observable effect: the observer receives different secret values
    // reason: an equal authorized release does not retire the obligation
    // preflight expectation: distinguish EqualAuthorized from unequal retirement
    llvm.call @sps_transfer_equal_release_observer(%secret) {
      sps.contract_ref = "observer-transfer",
      sps.transfer_destination = "observer-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.return
  }
}
