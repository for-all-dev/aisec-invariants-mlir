// RUN: %mlir-opt %s | %FileCheck %s
// RUN: %mlir-opt %s --verify-diagnostics
//
// case: redis-py canceled-connection reuse analogue
// classification: reduced-runtime-model
// c source: ../c/redis_pool_reuse_bad.c
// upstream GitHub source: https://github.com/redis/redis-py/blob/318b114f4da9846a2a7c150e1fb702e9bebd9fdf/redis/asyncio/cluster.py#L997-L1009
// upstream revision: 318b114f4da9846a2a7c150e1fb702e9bebd9fdf
// secret: %response_owned_by_a, confidential to actor A
// public: %response_owned_by_b and %request_a_was_cancelled
// expected outcome: unsafe
// observer/model: reduced-sequential-cross-actor-response
// reason id: cross-domain-stale-state
// outstanding obligations: none
// evidence boundary: L1 reduced return-flow model; cancellation, pooling, and concurrency applicability is L4
//
// CHECK-LABEL: llvm.func @redis_pool_reuse_bad
// CHECK-SAME: %[[A:[a-zA-Z0-9_]+]]: i32, %[[B:[a-zA-Z0-9_]+]]: i32, %[[CANCEL:[a-zA-Z0-9_]+]]: i32
// CHECK: %[[ONE:[0-9]+]] = llvm.mlir.constant(1 : i32) : i32
// CHECK: %[[ZERO:[0-9]+]] = llvm.mlir.constant(0 : i32) : i32
// CHECK: %[[CANCEL_BIT:[0-9]+]] = llvm.and %[[CANCEL]], %[[ONE]]
// CHECK: %[[CANCELLED:[0-9]+]] = llvm.icmp "ne" %[[CANCEL_BIT]], %[[ZERO]] : i32
// CHECK: llvm.cond_br %[[CANCELLED]],
// CHECK: llvm.return %[[A]] : i32
// CHECK: llvm.return %[[B]] : i32
module {
  llvm.func @redis_pool_reuse_bad(
      %response_owned_by_a: i32,
      %response_owned_by_b: i32,
      %request_a_was_cancelled: i32) -> i32 {
    %one = llvm.mlir.constant(1 : i32) : i32
    %zero = llvm.mlir.constant(0 : i32) : i32
    %cancel_bit = llvm.and %request_a_was_cancelled, %one : i32
    %cancelled = llvm.icmp "ne" %cancel_bit, %zero : i32
    llvm.cond_br %cancelled, ^stale, ^fresh
  ^stale:
    // CONFIDENTIALITY ERROR: cross-actor response return
    // secret source: %response_owned_by_a belongs only to actor A
    // observable effect: actor B receives the function's returned response
    // reason: connection reuse routes A's unread response to B after cancellation
    // detection boundary: L1 catches this model; the exact async race needs future runtime semantics
    // expected-error @+1 {{cross-domain-stale-state}}
    llvm.return %response_owned_by_a : i32
  ^fresh:
    llvm.return %response_owned_by_b : i32
  }
}
