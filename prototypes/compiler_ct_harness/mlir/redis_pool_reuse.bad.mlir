// case: redis-py canceled-connection reuse analogue
// classification: reduced-runtime-model
// c source: ../c/redis_pool_reuse_bad.c
// upstream GitHub source: https://github.com/redis/redis-py/blob/318b114f4da9846a2a7c150e1fb702e9bebd9fdf/redis/asyncio/cluster.py#L997-L1009
// upstream revision: 318b114f4da9846a2a7c150e1fb702e9bebd9fdf
// secret: %response_owned_by_a, confidential to actor A
// public: %response_owned_by_b and %request_a_was_cancelled
// expected verdict: reject for the reduced model
// exact incident boundary: unsupported-currently; exact incident needs cancellation, pool, and concurrency semantics
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
    llvm.return %response_owned_by_a : i32
  ^fresh:
    llvm.return %response_owned_by_b : i32
  }
}
