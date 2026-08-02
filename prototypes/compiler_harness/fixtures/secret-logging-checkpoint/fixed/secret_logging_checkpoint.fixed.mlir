// RUN: %checkpoint-runner run --snapshot fixtures/secret-logging-checkpoint/fixed/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/secret-logging-checkpoint/fixed/secret_logging_checkpoint.fixed.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic public-log and public-artifact sink summaries
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @secret_logging_checkpoint_fixed(
      %service_account_token: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %private_state: !llvm.ptr,
      %public_log: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"},
      %public_checkpoint: !llvm.ptr {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"}) {
    llvm.store %service_account_token, %private_state : i32, !llvm.ptr
    %zero = llvm.mlir.constant(0 : i32) : i32
    // PREFLIGHT CONTROL: redact the public log field
    // secret source: %service_account_token remains only in %private_state
    // safe effect: log readers observe the same public zero sentinel
    // reason: %zero has no data dependence on the token
    // preflight expectation: direct preflight diagnostic public-log sink check passes
    llvm.store %zero, %public_log {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    // PREFLIGHT CONTROL: redact the public checkpoint field
    // secret source: %service_account_token remains only in %private_state
    // safe effect: artifact readers observe the same public zero sentinel
    // reason: %zero has no data dependence on the token
    // preflight expectation: direct preflight diagnostic public-artifact sink check passes
    llvm.store %zero, %public_checkpoint {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
