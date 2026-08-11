// RUN: %checkpoint-runner run --snapshot fixtures/secret-logging-checkpoint/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/secret-logging-checkpoint/bad/secret_logging_checkpoint.bad.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic public-log and public-artifact sink summaries
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @secret_logging_checkpoint_bad(
      %service_account_token: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %private_state: !llvm.ptr,
      %public_log: !llvm.ptr {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"},
      %public_checkpoint: !llvm.ptr {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"}) {
    llvm.store %service_account_token, %private_state : i32, !llvm.ptr
    // PREFLIGHT FINDING: secret written to a public log
    // secret source: %service_account_token contains authentication material
    // observable effect: log readers can inspect the value stored at %public_log
    // reason: the public store operand is exactly the secret token
    // preflight expectation: direct preflight diagnostic sink violation with a public-log summary
    llvm.store %service_account_token, %public_log {sps.fixture_refs = ["snapshot.public[0]"], sps.sink_class = "public"} : i32, !llvm.ptr
    // PREFLIGHT FINDING: secret exported in a public checkpoint
    // secret source: %service_account_token contains authentication material
    // observable effect: artifact-store readers can inspect %public_checkpoint
    // reason: serialization copies the secret into a public persistent artifact
    // preflight expectation: direct preflight diagnostic sink violation with a public-artifact summary
    llvm.store %service_account_token, %public_checkpoint {sps.fixture_refs = ["snapshot.public[1]"], sps.sink_class = "public"} : i32, !llvm.ptr
    llvm.return
  }
}
