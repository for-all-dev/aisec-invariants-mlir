// RUN: %mlir-opt %s | %FileCheck %s
//
// scope note: preflight diagnostic reduced return-flow model; no async cancellation,
// pooling, or concurrency claim is made by this sequential Rev4 fixture
// annotation boundary: sps.label/sps.sink_class are unary preflight hints;
// sps.fixture_refs/sps.observable_candidate are review locators; snapshot/sidecars are authoritative.
//
// CHECK-LABEL: llvm.func @redis_pool_reuse_fixed
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"}, %[[B:[a-zA-Z0-9_]+]]: i32, %[[CANCEL:[a-zA-Z0-9_]+]]: i32
// CHECK-NOT: llvm.cond_br
// CHECK-NOT: llvm.return {{.*}}%[[A]]
// CHECK: llvm.return {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["return"], sps.sink_class = "public"} %[[B]] : i32
// CHECK-NOT: llvm.cond_br
// CHECK-NOT: llvm.return {{.*}}%[[A]]
module {
  llvm.func @redis_pool_reuse_fixed(
      %response_owned_by_a: i32 {sps.fixture_refs = ["snapshot.secret[0]"], sps.label = "high"},
      %response_owned_by_b: i32,
      %request_a_was_cancelled: i32) -> i32 {
    // PREFLIGHT CONTROL: return only actor B's response
    // secret source: %response_owned_by_a is deliberately unused
    // safe effect: actor B observes %response_owned_by_b for every A response
    // reason: stale connection state cannot influence the returned value
    // preflight expectation: preflight diagnostic passes this model; exact async correctness is outside the fixture claim
    llvm.return {sps.fixture_refs = ["snapshot.public[0]"], sps.observable_candidate = ["return"], sps.sink_class = "public"} %response_owned_by_b : i32
  }
}
