// RUN: %checkpoint-runner run --snapshot fixtures/audience-world/authorized/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/audience-world/authorized/audience_world_authorized.mlir --records %t.checkpoints

// World authorization includes the empty coalition. The unequal release
// retires the corresponding obligation before the public transfer.
module {
  llvm.func @llvm.sps.release(i32)
  llvm.func @sps_transfer_world_endpoint(i32)

  llvm.func @audience_world_authorized(
      %secret: i32 {sps.component_ref = "secret", sps.label = "high"}) {
    %mask = llvm.mlir.constant(255 : i32) : i32
    %released = llvm.and %secret, %mask : i32
    llvm.call @llvm.sps.release(%released) {
      sps.release_ref = "world-class",
      sps.site_alias = "world-class"
    } : (i32) -> ()
    llvm.call @sps_transfer_world_endpoint(%released) {
      sps.contract_ref = "world-transfer",
      sps.transfer_destination = "world-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.return
  }
}
