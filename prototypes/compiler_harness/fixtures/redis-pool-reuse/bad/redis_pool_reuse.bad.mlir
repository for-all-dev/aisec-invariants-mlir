// RUN: %checkpoint-runner run --snapshot fixtures/redis-pool-reuse/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.modeled.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.modeled.mlir
// RUN: %checkpoint-runner finalize --test fixtures/redis-pool-reuse/bad/redis_pool_reuse.bad.mlir --records %t.checkpoints

//
// scope note: preflight diagnostic reduced return-flow model; no async cancellation,
// pooling, or concurrency claim is made by this sequential Rev4 fixture
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
module {
  llvm.func @redis_pool_reuse_bad(
      %response_owned_by_a: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %response_owned_by_b: i32,
      %request_a_was_cancelled: i32) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %zero = llvm.mlir.constant(0 : i32) : i32
    %cancel_bit = llvm.and %request_a_was_cancelled, %one : i32
    %cancelled = llvm.icmp "ne" %cancel_bit, %zero : i32
    llvm.cond_br %cancelled, ^stale, ^fresh
  ^stale:
    // PREFLIGHT FINDING: cross-actor response return
    // secret source: %response_owned_by_a belongs only to actor A
    // observable effect: actor B receives the function's returned response
    // reason: connection reuse routes A's unread response to B after cancellation
    // preflight expectation: preflight diagnostic catches this model; the exact async race is outside the fixture claim
    llvm.return {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["return"], sps.sink_class = "public"} %response_owned_by_a : i32
  ^fresh:
    llvm.return {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["return"], sps.sink_class = "public"} %response_owned_by_b : i32
  }
}
