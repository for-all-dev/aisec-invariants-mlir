// RUN: %checkpoint-runner run --snapshot fixtures/audience-mismatch/authorized-audience/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/audience-mismatch/authorized-audience/audience_mismatch_authorized.mlir --records %t.checkpoints

//
// Policy counterfactual to audience-mismatch/bad. The program deliberately
// retains both transfers; only the authoritative release audience changes.
// This is not a program repair and therefore is not named "fixed".
//
module {
  llvm.func @llvm.sps.release(i32)
  llvm.func @sps_transfer_authorized_alice(i32)
  llvm.func @sps_transfer_authorized_bob(i32)

  llvm.func @audience_mismatch_authorized(
      %logits: i32 {
        sps.component_ref = "logits",
        sps.fixture_refs = ["secret:logits"],
        sps.label = "high"}) {
    %mask = llvm.mlir.constant(255 : i32) : i32
    %released = llvm.and %logits, %mask : i32
    llvm.call @llvm.sps.release(%released) {
      sps.fixture_refs = ["release:masked-class"],
      sps.release_ref = "masked-class",
      sps.site_alias = "masked-class"
    } : (i32) -> ()
    llvm.call @sps_transfer_authorized_alice(%released) {
      sps.contract_ref = "transfer-alice",
      sps.transfer_destination = "alice-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.call @sps_transfer_authorized_bob(%released) {
      sps.contract_ref = "transfer-bob",
      sps.transfer_destination = "bob-endpoint",
      sps.transfer_source = "compute"
    } : (i32) -> ()
    llvm.return
  }
}
