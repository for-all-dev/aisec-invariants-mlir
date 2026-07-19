/*
 * Small host-side smoke tests for the confidentiality harness.
 *
 * The crypto reductions are checked as functional bad/fixed pairs over small
 * domains or boundary vectors. The semantic harnesses check the authorized
 * result plus a concrete bad-observation witness, since the fixed public sink
 * is intentionally redacted.
 */

#include <stdint.h>

void clangover_poly_frommsg_vulnerable(int16_t out[256],
                                       const uint8_t msg[32]);
void clangover_poly_frommsg_fixed(int16_t out[256], const uint8_t msg[32]);

uint8_t kyberslash1_poly_tomsg_vulnerable(uint16_t coefficient);
uint8_t kyberslash1_poly_tomsg_fixed(uint16_t coefficient);
uint8_t kyberslash2_compress_vulnerable(uint16_t coefficient);
uint8_t kyberslash2_compress_fixed(uint16_t coefficient);

uint32_t wolfssl_3580_mask_vulnerable(const uint32_t table[16],
                                      uint32_t table_index);
uint32_t wolfssl_3580_mask_fixed(const uint32_t table[16],
                                 uint32_t table_index);
uint64_t wolfssl_3579_mul_vulnerable(uint64_t secret_a, uint64_t secret_b);
uint64_t wolfssl_3579_mul_fixed(uint64_t secret_a, uint64_t secret_b);

uint32_t breach_compressed_length_bad(uint8_t secret_byte,
                                      uint8_t public_guess,
                                      uint32_t encrypted_body,
                                      uint32_t *public_wire_length);
uint32_t breach_compressed_length_fixed(uint8_t secret_byte,
                                        uint8_t public_guess,
                                        uint32_t encrypted_body,
                                        uint32_t *public_wire_length);
uint32_t ckks_unsafe_release_bad(uint32_t raw_approximate_plaintext,
                                 uint32_t certified_public_value,
                                 uint32_t certificate_ok,
                                 uint32_t *public_release);
uint32_t ckks_unsafe_release_fixed(uint32_t raw_approximate_plaintext,
                                   uint32_t certified_public_value,
                                   uint32_t certificate_ok,
                                   uint32_t *public_release);
uint32_t dynamic_kv_length_bad(uint32_t secret_length,
                               uint32_t private_result,
                               uint32_t *public_allocation_count,
                               uint32_t *public_iteration_count);
uint32_t dynamic_kv_length_fixed(uint32_t secret_length,
                                 uint32_t private_result,
                                 uint32_t *public_allocation_count,
                                 uint32_t *public_iteration_count);
uint32_t explicit_error_oracle_bad(uint32_t padding_is_valid,
                                   uint32_t authorized_plaintext_length,
                                   uint32_t *public_status);
uint32_t explicit_error_oracle_fixed(uint32_t padding_is_valid,
                                     uint32_t authorized_plaintext_length,
                                     uint32_t *public_status);
uint32_t leftoverlocals_scratch_bad(uint32_t prior_tenant_secret,
                                    uint32_t next_tenant_public_value,
                                    uint32_t *shared_scratch,
                                    uint32_t *next_tenant_output);
uint32_t leftoverlocals_scratch_fixed(uint32_t prior_tenant_secret,
                                      uint32_t next_tenant_public_value,
                                      uint32_t *shared_scratch,
                                      uint32_t *next_tenant_output);
uint32_t redis_pool_reuse_bad(uint32_t response_owned_by_a,
                              uint32_t response_owned_by_b,
                              uint32_t request_a_was_cancelled);
uint32_t redis_pool_reuse_fixed(uint32_t response_owned_by_a,
                                uint32_t response_owned_by_b,
                                uint32_t request_a_was_cancelled);
uint32_t secret_embedding_index_bad(const uint32_t table[16],
                                    uint32_t secret_index);
uint32_t secret_embedding_index_fixed(const uint32_t table[16],
                                      uint32_t secret_index);
void secret_logging_checkpoint_bad(uint32_t service_account_token,
                                   uint32_t *private_state,
                                   uint32_t *public_log,
                                   uint32_t *public_checkpoint);
void secret_logging_checkpoint_fixed(uint32_t service_account_token,
                                     uint32_t *private_state,
                                     uint32_t *public_log,
                                     uint32_t *public_checkpoint);
uint32_t wrong_host_fhe_reveal_bad(uint32_t ciphertext_handle,
                                   uint32_t revealed_plaintext,
                                   uint32_t *authorized_client_plaintext,
                                   uint32_t *unauthorized_server_plaintext);
uint32_t wrong_host_fhe_reveal_fixed(uint32_t ciphertext_handle,
                                     uint32_t revealed_plaintext,
                                     uint32_t *authorized_client_plaintext,
                                     uint32_t *unauthorized_server_plaintext);
void wrong_party_plaintext_bad(uint32_t plaintext,
                               uint32_t *authorized_mailbox,
                               uint32_t *unauthorized_mailbox);
void wrong_party_plaintext_fixed(uint32_t plaintext,
                                 uint32_t *authorized_mailbox,
                                 uint32_t *unauthorized_mailbox);

static int failures;

static void expect_u64(const char *name, uint64_t got, uint64_t want) {
  (void)name;
  if (got != want) {
    ++failures;
  }
}

static void check_clangover(void) {
  uint8_t msg[32] = {0};
  int16_t bad[256] = {0};
  int16_t fixed[256] = {0};
  for (unsigned value = 0; value < 256; ++value) {
    msg[0] = (uint8_t)value;
    clangover_poly_frommsg_vulnerable(bad, msg);
    clangover_poly_frommsg_fixed(fixed, msg);
    for (unsigned i = 0; i < 256; ++i)
      expect_u64("clangover output", (uint16_t)bad[i], (uint16_t)fixed[i]);
  }
}

static void check_kyberslash(void) {
  for (uint32_t c = 0; c < 3329u; ++c) {
    expect_u64("kyberslash1", kyberslash1_poly_tomsg_vulnerable((uint16_t)c),
               kyberslash1_poly_tomsg_fixed((uint16_t)c));
    expect_u64("kyberslash2", kyberslash2_compress_vulnerable((uint16_t)c),
               kyberslash2_compress_fixed((uint16_t)c));
  }
}

static void check_wolfssl(void) {
  uint32_t table[16];
  uint64_t values[] = {0ull, 1ull, 2ull, 3ull, 0xffffffffull,
                       0x100000000ull, 0xffffffffffffffffull};

  for (unsigned i = 0; i < 16; ++i)
    table[i] = 0x1000u + i * 17u;
  for (uint32_t i = 0; i < 20; ++i)
    expect_u64("wolfssl 3580", wolfssl_3580_mask_vulnerable(table, i),
               wolfssl_3580_mask_fixed(table, i));

  for (unsigned i = 0; i < sizeof(values) / sizeof(values[0]); ++i)
    for (unsigned j = 0; j < sizeof(values) / sizeof(values[0]); ++j)
      expect_u64("wolfssl 3579", wolfssl_3579_mul_vulnerable(values[i], values[j]),
                 wolfssl_3579_mul_fixed(values[i], values[j]));
}

static void check_semantic_harnesses(void) {
  uint32_t a = 0, b = 0, c = 0, d = 0;
  uint32_t table[16];

  wrong_party_plaintext_bad(77u, &a, &b);
  wrong_party_plaintext_fixed(77u, &c, &d);
  expect_u64("wrong party authorized", a, c);
  expect_u64("wrong party bad leak", b, 77u);
  expect_u64("wrong party fixed redaction", d, 0u);

  secret_logging_checkpoint_bad(0xaceu, &a, &b, &c);
  secret_logging_checkpoint_fixed(0xaceu, &d, &a, &b);
  expect_u64("logging private state", d, 0xaceu);
  expect_u64("logging fixed log", a, 0u);
  expect_u64("logging fixed checkpoint", b, 0u);
  expect_u64("logging bad checkpoint", c, 0xaceu);

  expect_u64("explicit oracle return",
             explicit_error_oracle_bad(1u, 123u, &a),
             explicit_error_oracle_fixed(1u, 123u, &b));
  expect_u64("explicit oracle bad status", a, 0u);
  expect_u64("explicit oracle fixed status", b, 0u);
  (void)explicit_error_oracle_bad(0u, 123u, &a);
  expect_u64("explicit oracle witness", a, 1u);

  expect_u64("breach return",
             breach_compressed_length_bad(7u, 7u, 999u, &a),
             breach_compressed_length_fixed(7u, 7u, 999u, &b));
  expect_u64("breach bad length", a, 31u);
  expect_u64("breach fixed length", b, 32u);

  for (unsigned i = 0; i < 16; ++i)
    table[i] = 0x3000u + i;
  for (unsigned i = 0; i < 16; ++i)
    expect_u64("embedding value", secret_embedding_index_bad(table, i),
               secret_embedding_index_fixed(table, i));

  expect_u64("dynamic return", dynamic_kv_length_bad(5u, 42u, &a, &b),
             dynamic_kv_length_fixed(5u, 42u, &c, &d));
  expect_u64("dynamic bad allocation", a, 5u);
  expect_u64("dynamic fixed allocation", c, 64u);

  expect_u64("wrong-host return",
             wrong_host_fhe_reveal_bad(9u, 1234u, &a, &b),
             wrong_host_fhe_reveal_fixed(9u, 1234u, &c, &d));
  expect_u64("wrong-host authorized", a, c);
  expect_u64("wrong-host fixed unauthorized", d, 0u);

  expect_u64("ckks return", ckks_unsafe_release_bad(55u, 12u, 1u, &a),
             ckks_unsafe_release_fixed(55u, 12u, 1u, &b));
  expect_u64("ckks bad release", a, 55u);
  expect_u64("ckks fixed release", b, 12u);

  expect_u64("leftover return", leftoverlocals_scratch_bad(99u, 7u, &a, &b),
             leftoverlocals_scratch_fixed(99u, 7u, &c, &d));
  expect_u64("leftover bad leak", b, 99u);
  expect_u64("leftover fixed output", d, 7u);

  expect_u64("redis normal behavior", redis_pool_reuse_bad(11u, 22u, 0u),
             redis_pool_reuse_fixed(11u, 22u, 0u));
  expect_u64("redis stale witness", redis_pool_reuse_bad(11u, 22u, 1u), 11u);
  expect_u64("redis fixed response", redis_pool_reuse_fixed(11u, 22u, 1u), 22u);
}

int main(void) {
  check_clangover();
  check_kyberslash();
  check_wolfssl();
  check_semantic_harnesses();

  if (failures != 0)
    return 1;
  return 0;
}
