// case: redis-py canceled-connection reuse analogue
// classification: reduced-runtime-model
// c source: ../c/redis_pool_reuse_fixed.c
// upstream GitHub source: https://github.com/redis/redis-py/commit/66a4d6b2a493dd3a20cc299ab5fef3c14baad965
// upstream revision: 66a4d6b2a493dd3a20cc299ab5fef3c14baad965
// secret: %response_owned_by_a, confidential to actor A
// public: %response_owned_by_b and %request_a_was_cancelled
// expected verdict: pass for the reduced model
// exact incident boundary: unsupported-currently; exact incident needs cancellation, pool, and concurrency semantics
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
