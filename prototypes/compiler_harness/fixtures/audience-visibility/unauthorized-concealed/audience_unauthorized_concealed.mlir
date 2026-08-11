// RUN: %checkpoint-runner run --snapshot fixtures/audience-visibility/unauthorized-concealed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/audience-visibility/unauthorized-concealed/audience_unauthorized_concealed.mlir --records %t.checkpoints

// An unauthorized release is concealed when neither Audience nor LocVisible
// holds. It does not retire the obligation, but concealment alone is not Bad.
module {
  llvm.func @llvm.sps.release(i32)
  llvm.func @sps_transfer_concealed_endpoint(i32)

  llvm.func @audience_unauthorized_concealed(
      %secret: i32 {sps.component_ref = "secret", sps.label = "high"}) {
    %mask = llvm.mlir.constant(255 : i32) : i32
    %released = llvm.and %secret, %mask : i32
    llvm.call @llvm.sps.release(%released) {
      sps.release_ref = "alice-class",
      sps.site_alias = "alice-class"
    } : (i32) -> ()
    llvm.call @sps_transfer_concealed_endpoint(%released) {
      sps.contract_ref = "concealed-transfer",
      sps.transfer_destination = "concealed-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.return
  }
}
