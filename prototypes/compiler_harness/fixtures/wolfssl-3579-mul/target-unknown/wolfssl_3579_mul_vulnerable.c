/*
 * Case: wolfSSL CVE-2026-3579 RV32I 64-bit multiply vulnerable reduction
 *
 * Upstream repository:
 *   https://github.com/wolfSSL/wolfssl
 *
 * Original vulnerable code:
 *   https://github.com/wolfSSL/wolfssl/blob/b6fbfad945d4b98fce619b6e5b6561b3eca1205b/wolfcrypt/src/sp_c32.c
 *
 * Original fixed code:
 *   https://github.com/wolfSSL/wolfssl/tree/8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5/wolfcrypt/src
 *
 * Upstream symbol:
 *   sp_256_mul_9 and related SP arithmetic
 *
 * Upstream vulnerable revision:
 *   b6fbfad945d4b98fce619b6e5b6561b3eca1205b
 *
 * Upstream fixed revision:
 *   8a5c1c7af1ec791eeb4a8c183658a6e926e6e1a5
 *
 * Reduction classification:
 *   independently-written-equivalent-reduction
 *
 * Relationship to upstream:
 *   Retains only the security-relevant source operation: a 64-bit multiply
 *   involving secret operands on RV32I without the M extension.
 *
 * Secret inputs:
 *   secret_a and secret_b
 *
 * Public inputs:
 *   selected target/helper profile; the bad MLIR fixture names
 *   affected-rv32i-muldi3-v2
 *
 * Expected confidentiality issue:
 *   Backend legalization emits __muldi3. The call is unsafe under the named
 *   affected profile's operand-dependent latency contract; without a helper
 *   timing summary, the confidentiality verdict is unknown rather than safe.
 *   Applying that affected profile to a real target remains conditional until
 *   deployment evidence validates the helper-timing evidence.
 *
 * Canonical compiler command:
 *   clang -I../../../include -O3 --target=riscv32-unknown-elf -march=rv32i -mabi=ilp32 -S
 * wolfssl_3579_mul_vulnerable.c
 *
 * License note:
 *   This independently written reduction contains no copied wolfSSL source.
 */
#include <sps/annotations.h>
typedef unsigned long long uint64_t;

SPS_ENTRY("wolfssl_3579_mul_rv32_unknown_model")
SPS_RETURN_OUTPUT("return")
__attribute__((noinline)) uint64_t
wolfssl_3579_mul_vulnerable(uint64_t secret_a SPS_COMPONENT("secret-a"),
                            uint64_t secret_b SPS_COMPONENT("secret-b")) {
  return secret_a * secret_b;
}
