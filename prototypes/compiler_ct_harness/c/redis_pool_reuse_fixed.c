/*
 * Case: redis-py canceled-connection reuse (fixed reduced analogue)
 *
 * Upstream repository:
 *   https://github.com/redis/redis-py
 *
 * Original C source:
 *   none -- the original implementation is Python and uses async cancellation
 *
 * Original vulnerable code:
 *   https://github.com/redis/redis-py/blob/318b114f4da9846a2a7c150e1fb702e9bebd9fdf/redis/asyncio/cluster.py#L997-L1009
 *
 * Original fixed code:
 *   https://github.com/redis/redis-py/commit/66a4d6b2a493dd3a20cc299ab5fef3c14baad965
 *
 * Regression test:
 *   https://github.com/redis/redis-py/blob/e1017fd77afd2f56dca90f986fc82e398e518a26/tests/test_asyncio/test_cwe_404.py#L48-L79
 *
 * Upstream symbol:
 *   redis.asyncio.cluster.ClusterNode.execute_command
 *
 * Upstream vulnerable revision:
 *   318b114f4da9846a2a7c150e1fb702e9bebd9fdf
 *
 * Upstream fixed revision:
 *   66a4d6b2a493dd3a20cc299ab5fef3c14baad965
 *
 * Reduction classification:
 *   reduced-runtime-model
 *
 * Relationship to upstream:
 *   Models discarding the stale response before actor B uses the connection.
 *   It does not reproduce or prove the correctness of async cancellation.
 *
 * Secret inputs:
 *   response_owned_by_a
 *
 * Public inputs:
 *   response_owned_by_b and request_a_was_cancelled
 *
 * Expected confidentiality repair:
 *   Actor B always receives the response owned by actor B.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -c redis_pool_reuse_fixed.c
 *
 * License note:
 *   This independently written C model contains no redis-py source code.
 */

#include <stdint.h>

uint32_t redis_pool_reuse_fixed(uint32_t response_owned_by_a,
                                uint32_t response_owned_by_b,
                                uint32_t request_a_was_cancelled) {
  (void)response_owned_by_a;
  (void)request_a_was_cancelled;
  return response_owned_by_b;
}
