// RUN: %checkpoint-runner run --snapshot fixtures/audience-joint/singleton-visible-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/audience-joint/singleton-visible-bad/audience_joint_singleton_visible_bad.mlir --records %t.checkpoints

// Joint audience means Alice AND Bob, not Alice OR Bob. The {alice} product
// can see the transfer but cannot retire the release obligation.
module {
  llvm.func @llvm.sps.release(i32)
  llvm.func @sps_transfer_joint_to_alice(i32)

  llvm.func @audience_joint_singleton_visible_bad(
      %logits: i32 {sps.component_ref = "logits", sps.label = "high"}) {
    %mask = llvm.mlir.constant(255 : i32) : i32
    %released = llvm.and %logits, %mask : i32
    llvm.call @llvm.sps.release(%released) {
      sps.release_ref = "joint-class",
      sps.site_alias = "joint-class"
    } : (i32) -> ()
    // PREFLIGHT FINDING: joint-only release delivered to one member
    // secret source: %released is derived from concealed %logits
    // observable effect: Alice receives different class values in the two lanes
    // reason: the singleton Alice coalition does not satisfy the joint audience
    // preflight expectation: preserve the Alice destination for coalition-indexed checking
    llvm.call @sps_transfer_joint_to_alice(%released) {
      sps.contract_ref = "transfer-alice",
      sps.transfer_destination = "alice-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.return
  }
}
