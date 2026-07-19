/*
 * Case: redis-py canceled-connection reuse (reduced analogue)
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
 *   Sequentially models an unread response from actor A being delivered to
 *   actor B after cancellation. It does not reproduce the async race.
 *
 * Secret inputs:
 *   response_owned_by_a
 *
 * Public inputs:
 *   response_owned_by_b and request_a_was_cancelled
 *
 * Expected confidentiality issue:
 *   Actor B receives actor A's response when the stale connection is reused.
 *
 * Canonical compiler command:
 *   clang -std=c11 -Wall -Wextra -Werror -c redis_pool_reuse_bad.c
 *
 * License note:
 *   This independently written C model contains no redis-py source code.
 */

#include <stdint.h>

uint32_t redis_pool_reuse_bad(uint32_t response_owned_by_a,
                              uint32_t response_owned_by_b,
                              uint32_t request_a_was_cancelled) {
  return (request_a_was_cancelled & 1u) != 0u ? response_owned_by_a
                                              : response_owned_by_b;
}
