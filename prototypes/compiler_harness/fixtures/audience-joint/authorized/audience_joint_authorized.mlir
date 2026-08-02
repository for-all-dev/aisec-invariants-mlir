// RUN: %checkpoint-runner run --snapshot fixtures/audience-joint/authorized/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/audience-joint/authorized/audience_joint_authorized.mlir --records %t.checkpoints

// Joint audience means Alice AND Bob. The endpoint uses the same joint basis,
// so singleton products project no transfer payload and the joint product is
// authorized when it does project the payload.
module {
  llvm.func @llvm.sps.release(i32)
  llvm.func @sps_transfer_joint_endpoint(i32)

  llvm.func @audience_joint_authorized(
      %logits: i32 {sps.component_ref = "logits", sps.label = "high"}) {
    %mask = llvm.mlir.constant(255 : i32) : i32
    %released = llvm.and %logits, %mask : i32
    llvm.call @llvm.sps.release(%released) {
      sps.release_ref = "joint-class",
      sps.site_alias = "joint-class"
    } : (i32) -> ()
    llvm.call @sps_transfer_joint_endpoint(%released) {
      sps.contract_ref = "transfer-joint",
      sps.transfer_destination = "joint-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.return
  }
}
