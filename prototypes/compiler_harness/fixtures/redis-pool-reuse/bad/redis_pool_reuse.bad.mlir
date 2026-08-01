// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic reduced return-flow model; no async cancellation,
// pooling, or concurrency claim is made by this sequential Rev4 fixture
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @redis_pool_reuse_bad
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[B:[a-zA-Z0-9_]+]]: i32, %[[CANCEL:[a-zA-Z0-9_]+]]: i32
// CHECK: %[[ONE:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[CANCEL_BIT:[0-9]+]] = llvm.and %[[CANCEL]], %[[ONE]]
// CHECK: %[[CANCELLED:[0-9]+]] = llvm.icmp "ne" %[[CANCEL_BIT]], %[[ZERO]] : i32
// CHECK: llvm.cond_br %[[CANCELLED]],
// CHECK: llvm.return {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["return"], sps.sink_class = "public"} %[[A]] : i32
// CHECK: llvm.return {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["return"], sps.sink_class = "public"} %[[B]] : i32
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
