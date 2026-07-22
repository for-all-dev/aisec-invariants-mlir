// RUN: %mlir-opt %s | %FileCheck %s
//
// case: redis-py canceled-connection reuse analogue
// classification: reduced-runtime-model
// c source: ../c/redis_pool_reuse_fixed.c
// upstream GitHub source: https://github.com/redis/redis-py/commit/66a4d6b2a493dd3a20cc299ab5fef3c14baad965
// upstream revision: 66a4d6b2a493dd3a20cc299ab5fef3c14baad965
// secret: %response_owned_by_a, confidential to actor A
// public: %response_owned_by_b and %request_a_was_cancelled
// expected outcome: verified
// observer/model: reduced-sequential-cross-actor-response
// reason id: cross-domain-state-reinitialized
// outstanding obligations: none
// evidence boundary: L1 reduced return-flow model; cancellation, pooling, and concurrency applicability is L4
//
// CHECK-LABEL: llvm.func @redis_pool_reuse_fixed
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i32, %[[B:[a-zA-Z0-9_]+]]: i32, %[[CANCEL:[a-zA-Z0-9_]+]]: i32
// CHECK-NOT: llvm.cond_br
// CHECK-NOT: llvm.return %[[A]]
// CHECK: llvm.return %[[B]] : i32
// CHECK-NOT: llvm.cond_br
// CHECK-NOT: llvm.return %[[A]]
module {
  llvm.func @redis_pool_reuse_fixed(
      %response_owned_by_a: i32,
      %response_owned_by_b: i32,
      %request_a_was_cancelled: i32) -> i32 {
    // CONFIDENTIALITY REPAIR: return only actor B's response
    // secret source: %response_owned_by_a is deliberately unused
    // safe effect: actor B observes %response_owned_by_b for every A response
    // reason: stale connection state cannot influence the returned value
    // detection boundary: L1 passes this model; exact async correctness remains a runtime obligation
    llvm.return %response_owned_by_b : i32
  }
}
