// RUN: %checkpoint-runner run --snapshot fixtures/audience-visibility/location-visible-bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/audience-visibility/location-visible-bad/audience_location_visible_bad.mlir --records %t.checkpoints

// Bob sees the release site because compute is Bob-visible. LocVisible exposes
// the value but does not authorize the release or retire its obligation.
module {
  llvm.func @llvm.sps.release(i32)

  llvm.func @audience_location_visible_bad(
      %secret: i32 {sps.component_ref = "secret", sps.label = "high"}) {
    %mask = llvm.mlir.constant(255 : i32) : i32
    %released = llvm.and %secret, %mask : i32
    // PREFLIGHT FINDING: unauthorized observer sees release value at its host
    // secret source: %released is derived from concealed %secret
    // observable effect: Bob sees unequal release bytes at the compute host
    // reason: location visibility reveals value but never grants authorization
    // preflight expectation: retain distinct audience and host-visibility predicates
    llvm.call @llvm.sps.release(%released) {
      sps.release_ref = "alice-class",
      sps.site_alias = "alice-class"
    } : (i32) -> ()
    llvm.return
  }
}
