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
uint8_t kyberslash1_poly_tomsg_target_bad(uint16_t coefficient);
uint8_t kyberslash2_compress_vulnerable(uint16_t coefficient);
uint8_t kyberslash2_compress_fixed(uint16_t coefficient);
uint8_t kyberslash2_compress_target_bad(uint16_t coefficient);

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
                                 uint32_t public_sanitizer_mask,
                                 uint32_t certificate_ok,
                                 uint32_t *public_release);
uint32_t ckks_unsafe_release_fixed(uint32_t raw_approximate_plaintext,
                                   uint32_t public_sanitizer_mask,
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
                                   uint32_t padding_error_detail,
                                   uint32_t authorized_plaintext_length,
                                   uint32_t *public_status,
                                   uint32_t *public_error_detail);
uint32_t explicit_error_oracle_fixed(uint32_t padding_is_valid,
                                     uint32_t padding_error_detail,
                                     uint32_t authorized_plaintext_length,
                                     uint32_t *public_status,
                                     uint32_t *public_error_detail);
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
                                   uint32_t revealed_plaintext);
uint32_t wrong_host_fhe_reveal_fixed(uint32_t ciphertext_handle,
                                     uint32_t revealed_plaintext);
void wrong_party_plaintext_bad(uint32_t plaintext);
void wrong_party_plaintext_fixed(uint32_t plaintext);

void abi_alias_missing_binding(unsigned secret, unsigned *p, unsigned *q,
                               unsigned *public_output);
void abi_alias_mayalias_overlap(unsigned secret, unsigned *p, unsigned *q,
                                unsigned *public_output);
void abi_alias_disjoint_control(unsigned secret, unsigned *p, unsigned *q,
                                unsigned *public_output);
void abi_alias_explicit_same_actual(unsigned secret, unsigned *shared,
                                    unsigned *public_output);
void alloca_size_high_count(int secret_bit, unsigned *public_sink);
void alloca_size_public_control(unsigned public_count, unsigned *public_sink);
void alloca_size_fixed_region_copy_bad(uint32_t secret, uint8_t *public_out);
uint32_t argmax_release_body(const int32_t logits[10]);
void audience_equal_release_then_leak_bad(unsigned secret);
void audience_joint_authorized(unsigned logits);
void audience_joint_singleton_visible_bad(unsigned logits);
void audience_location_visible_bad(unsigned secret);
void audience_mismatch_bad(unsigned logits);
void audience_mismatch_authorized(unsigned logits);
void audience_unauthorized_concealed(unsigned secret);
void audience_world_authorized(unsigned secret);
void bound_secret_trip_count_bad(int secret_count, unsigned *public_sink);
void bound_exhausted_public_loop(int public_count, unsigned *public_sink);
void bound_adequate_public_loop(int public_count, unsigned *public_sink);
uint64_t launder_scan_bad(int secret, uint64_t x, const uint64_t *p);
uint64_t launder_scan_folded_bad(int secret, uint64_t x, const uint64_t *p);
uint64_t launder_scan_fixed(int secret, uint64_t x, const uint64_t *p);
unsigned predecessor_choice_blockarg_bad(int secret_bit);
void prefix_causal_release_bad(unsigned secret);
unsigned identical_successor_control(int high_condition,
                                     unsigned public_value);
unsigned different_successor_bad(int high_condition, unsigned public_value);
unsigned xor_cancellation_control(unsigned secret);
unsigned xor_secret_output_bad(unsigned secret);
unsigned overwritten_slot_control(unsigned secret, unsigned public_value);
unsigned missing_overwrite_bad(unsigned secret, unsigned public_value);
unsigned offset_disjoint_control(unsigned char *buffer, unsigned secret_byte,
                                 unsigned public_value);
unsigned offset_overlap_bad(unsigned char *buffer, unsigned secret_byte,
                            unsigned public_value);
void pointer_rebinding_disjoint_select_bad(uint32_t secret_selector,
                                           const uint8_t *left,
                                           const uint8_t *right,
                                           uint8_t *private_result);
void pointer_rebinding_same_allocation_control(uint32_t secret_selector,
                                               const uint8_t *left,
                                               const uint8_t *right,
                                               uint8_t *private_result);
void pointer_rebinding_pointer_spill_unsupported(uint32_t secret_selector,
                                                 const uint8_t *left,
                                                 const uint8_t *right,
                                                 uint8_t *private_result);
uint32_t sps_release_invalid_callable(uint32_t raw, uint32_t public_mask);
void release_carrier(uint32_t raw, uint32_t mask_a, uint32_t mask_b,
                     uint32_t *sink);
uint32_t sha256_round_release_body(uint32_t e, uint32_t f, uint32_t g,
                                   uint32_t h, uint32_t k, uint32_t w);

static int failures;
static uint32_t transfer_audience_alice;
static uint32_t transfer_audience_bob;
static uint32_t transfer_authorized_alice;
static uint32_t transfer_authorized_bob;
static uint32_t transfer_concealed_endpoint;
static uint32_t transfer_equal_release_observer;
static uint32_t transfer_joint_endpoint;
static uint32_t transfer_joint_to_alice;
static uint32_t transfer_world_endpoint;
static uint32_t transfer_fhe_authorized_client;
static uint32_t transfer_fhe_server;
static uint32_t transfer_party_authorized;
static uint32_t transfer_party_observer;
static uint32_t transfer_prefix_public;

/* Runtime-only endpoint realizations; fixture authoring keeps these external. */
void sps_transfer_audience_alice(uint32_t value) {
  transfer_audience_alice = value;
}

void sps_transfer_audience_bob(uint32_t value) {
  transfer_audience_bob = value;
}

void sps_transfer_authorized_alice(uint32_t value) {
  transfer_authorized_alice = value;
}

void sps_transfer_authorized_bob(uint32_t value) {
  transfer_authorized_bob = value;
}

void sps_transfer_concealed_endpoint(uint32_t value) {
  transfer_concealed_endpoint = value;
}

void sps_transfer_equal_release_observer(uint32_t value) {
  transfer_equal_release_observer = value;
}

void sps_transfer_joint_endpoint(uint32_t value) {
  transfer_joint_endpoint = value;
}

void sps_transfer_joint_to_alice(uint32_t value) {
  transfer_joint_to_alice = value;
}

void sps_transfer_world_endpoint(uint32_t value) {
  transfer_world_endpoint = value;
}

void sps_transfer_fhe_authorized_client(uint32_t value) {
  transfer_fhe_authorized_client = value;
}

void sps_transfer_fhe_server(uint32_t value) { transfer_fhe_server = value; }

void sps_transfer_party_authorized(uint32_t value) {
  transfer_party_authorized = value;
}

void sps_transfer_party_observer(uint32_t value) {
  transfer_party_observer = value;
}

void sps_transfer_prefix_public(uint32_t value) {
  transfer_prefix_public = value;
}

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
  for (unsigned position = 0; position < 32; ++position) {
    for (unsigned value = 0; value < 256; ++value) {
      msg[position] = (uint8_t)value;
      clangover_poly_frommsg_vulnerable(bad, msg);
      clangover_poly_frommsg_fixed(fixed, msg);
      for (unsigned i = 0; i < 256; ++i)
        expect_u64("clangover output", (uint16_t)bad[i], (uint16_t)fixed[i]);
    }
    msg[position] = 0;
  }
}

static void check_kyberslash(void) {
  for (uint32_t c = 0; c < 3329u; ++c) {
    expect_u64("kyberslash1", kyberslash1_poly_tomsg_vulnerable((uint16_t)c),
               kyberslash1_poly_tomsg_fixed((uint16_t)c));
    expect_u64("kyberslash1 target-control",
               kyberslash1_poly_tomsg_target_bad((uint16_t)c),
               kyberslash1_poly_tomsg_fixed((uint16_t)c));
    expect_u64("kyberslash2", kyberslash2_compress_vulnerable((uint16_t)c),
               kyberslash2_compress_fixed((uint16_t)c));
    expect_u64("kyberslash2 target-control",
               kyberslash2_compress_target_bad((uint16_t)c),
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
  uint32_t bad_status = 0, fixed_status = 0;
  uint32_t bad_detail = 0, fixed_detail = 0;
  uint32_t bad_status_alt = 0, fixed_status_alt = 0;
  uint32_t bad_detail_alt = 0, fixed_detail_alt = 0;
  uint32_t table[16];

  wrong_party_plaintext_bad(77u);
  expect_u64("wrong party authorized", transfer_party_authorized, 77u);
  expect_u64("wrong party bad leak", transfer_party_observer, 77u);
  wrong_party_plaintext_fixed(77u);
  expect_u64("wrong party fixed authorized", transfer_party_authorized, 77u);
  expect_u64("wrong party fixed redaction", transfer_party_observer, 0u);

  secret_logging_checkpoint_bad(0xaceu, &a, &b, &c);
  expect_u64("logging bad private state", a, 0xaceu);
  expect_u64("logging bad log", b, 0xaceu);
  expect_u64("logging bad checkpoint", c, 0xaceu);
  secret_logging_checkpoint_fixed(0xaceu, &d, &a, &b);
  expect_u64("logging private state", d, 0xaceu);
  expect_u64("logging fixed log", a, 0u);
  expect_u64("logging fixed checkpoint", b, 0u);

  expect_u64("explicit oracle return",
             explicit_error_oracle_bad(1u, 7u, 123u, &bad_status,
                                       &bad_detail),
             explicit_error_oracle_fixed(1u, 7u, 123u, &fixed_status,
                                         &fixed_detail));
  expect_u64("explicit oracle sanctioned bad status", bad_status, 0u);
  expect_u64("explicit oracle sanctioned fixed status", fixed_status, 0u);
  expect_u64("explicit oracle bad detail leak", bad_detail, 7u);
  expect_u64("explicit oracle fixed detail redaction", fixed_detail, 0u);

  (void)explicit_error_oracle_bad(0u, 11u, 123u, &bad_status, &bad_detail);
  (void)explicit_error_oracle_bad(0u, 29u, 123u, &bad_status_alt,
                                  &bad_detail_alt);
  (void)explicit_error_oracle_fixed(0u, 11u, 123u, &fixed_status,
                                    &fixed_detail);
  (void)explicit_error_oracle_fixed(0u, 29u, 123u, &fixed_status_alt,
                                    &fixed_detail_alt);
  expect_u64("explicit oracle bad authorized releases", bad_status,
             bad_status_alt);
  expect_u64("explicit oracle fixed authorized releases", fixed_status,
             fixed_status_alt);
  expect_u64("explicit oracle bad/fixed authorized status", bad_status,
             fixed_status);
  expect_u64("explicit oracle invalid status", bad_status, 1u);
  expect_u64("explicit oracle bad witness first detail", bad_detail, 11u);
  expect_u64("explicit oracle bad witness second detail", bad_detail_alt, 29u);
  expect_u64("explicit oracle fixed first detail", fixed_detail, 0u);
  expect_u64("explicit oracle fixed second detail", fixed_detail_alt, 0u);

  expect_u64("breach return",
             breach_compressed_length_bad(7u, 7u, 999u, &a),
             breach_compressed_length_fixed(7u, 7u, 999u, &b));
  expect_u64("breach bad length", a, 31u);
  expect_u64("breach fixed length", b, 32u);
  (void)breach_compressed_length_bad(8u, 7u, 999u, &c);
  (void)breach_compressed_length_fixed(8u, 7u, 999u, &d);
  expect_u64("breach bad mismatch witness", c, 32u);
  expect_u64("breach fixed mismatch length", d, 32u);

  for (unsigned i = 0; i < 16; ++i)
    table[i] = 0x3000u + i;
  for (unsigned i = 0; i < 16; ++i)
    expect_u64("embedding value", secret_embedding_index_bad(table, i),
               secret_embedding_index_fixed(table, i));
  for (unsigned i = 0; i < 16; ++i) {
    expect_u64("embedding wrapped value",
               secret_embedding_index_bad(table, i + 16u),
               secret_embedding_index_fixed(table, i + 16u));
    expect_u64("embedding high-bit value",
               secret_embedding_index_bad(table, 0xfffffff0u | i),
               secret_embedding_index_fixed(table, 0xfffffff0u | i));
  }

  expect_u64("dynamic return", dynamic_kv_length_bad(5u, 42u, &a, &b),
             dynamic_kv_length_fixed(5u, 42u, &c, &d));
  expect_u64("dynamic bad allocation", a, 5u);
  expect_u64("dynamic bad work count", b, 5u);
  expect_u64("dynamic fixed allocation", c, 64u);
  expect_u64("dynamic fixed work count", d, 64u);
  (void)dynamic_kv_length_bad(9u, 42u, &a, &b);
  (void)dynamic_kv_length_fixed(9u, 42u, &c, &d);
  expect_u64("dynamic second bad allocation", a, 9u);
  expect_u64("dynamic second bad work count", b, 9u);
  expect_u64("dynamic second fixed allocation", c, 64u);
  expect_u64("dynamic second fixed work count", d, 64u);

  expect_u64("wrong-host return",
             wrong_host_fhe_reveal_bad(9u, 1234u), 9u);
  expect_u64("wrong-host authorized", transfer_fhe_authorized_client, 1234u);
  expect_u64("wrong-host bad unauthorized leak", transfer_fhe_server, 1234u);
  expect_u64("wrong-host fixed return",
             wrong_host_fhe_reveal_fixed(9u, 1234u), 9u);
  expect_u64("wrong-host fixed authorized", transfer_fhe_authorized_client,
             1234u);
  expect_u64("wrong-host fixed unauthorized", transfer_fhe_server, 0u);

  expect_u64("ckks return", ckks_unsafe_release_bad(55u, 12u, 1u, &a),
             ckks_unsafe_release_fixed(55u, 12u, 1u, &b));
  expect_u64("ckks bad release", a, 55u);
  expect_u64("ckks fixed sanctioned release", b, 4u);
  (void)ckks_unsafe_release_bad(23u, 12u, 1u, &c);
  (void)ckks_unsafe_release_fixed(23u, 12u, 1u, &d);
  expect_u64("ckks release-relative bad witness", c, 23u);
  expect_u64("ckks equal sanctioned release", d, 4u);
  (void)ckks_unsafe_release_bad(55u, 12u, 0u, &a);
  (void)ckks_unsafe_release_fixed(55u, 12u, 0u, &b);
  expect_u64("ckks bad ignores failed certificate", a, 55u);
  expect_u64("ckks fixed failed certificate", b, 0u);

  expect_u64("leftover return", leftoverlocals_scratch_bad(99u, 7u, &a, &b),
             leftoverlocals_scratch_fixed(99u, 7u, &c, &d));
  expect_u64("leftover bad leak", b, 99u);
  expect_u64("leftover fixed output", d, 7u);

  expect_u64("redis normal behavior", redis_pool_reuse_bad(11u, 22u, 0u),
             redis_pool_reuse_fixed(11u, 22u, 0u));
  expect_u64("redis stale witness", redis_pool_reuse_bad(11u, 22u, 1u), 11u);
  expect_u64("redis fixed response", redis_pool_reuse_fixed(11u, 22u, 1u), 22u);
}

static void check_precision_controls(void) {
  unsigned char control_buffer[16] = {0};
  unsigned char bad_buffer[16] = {0};

  /*
   * These two sources are value-equivalent but intentionally differ in their
   * hand-authored MLIR control traces. Exercise both source branch edges here;
   * the fixture shape tests, not these value assertions, own that distinction.
   */
  expect_u64("identical successor false",
             identical_successor_control(0, 0x1111u), 0x1111u);
  expect_u64("identical successor true",
             identical_successor_control(1, 0x1111u), 0x1111u);
  expect_u64("different successor false",
             different_successor_bad(0, 0x1111u), 0x1111u);
  expect_u64("different successor true",
             different_successor_bad(1, 0x1111u), 0x1111u);

  /* Cancellation makes the control output independent of the secret. */
  expect_u64("xor cancellation first secret",
             xor_cancellation_control(0x2222u), 0u);
  expect_u64("xor cancellation second secret",
             xor_cancellation_control(0x3333u), 0u);
  expect_u64("xor secret-output first witness",
             xor_secret_output_bad(0x2222u), 0x2222u);
  expect_u64("xor secret-output second witness",
             xor_secret_output_bad(0x3333u), 0x3333u);

  /* A complete public overwrite removes the prior secret; omitting it leaks. */
  expect_u64("overwritten slot first secret",
             overwritten_slot_control(0x3333u, 0x4444u), 0x4444u);
  expect_u64("overwritten slot second secret",
             overwritten_slot_control(0x5555u, 0x4444u), 0x4444u);
  expect_u64("missing overwrite first witness",
             missing_overwrite_bad(0x3333u, 0x4444u), 0x3333u);
  expect_u64("missing overwrite second witness",
             missing_overwrite_bad(0x5555u, 0x4444u), 0x5555u);

  /* The control reloads public byte 8; the anti-control reloads secret byte 4. */
  expect_u64("offset-disjoint first secret",
             offset_disjoint_control(control_buffer, 0x55u, 0x66u), 0x66u);
  expect_u64("offset-disjoint first stored secret", control_buffer[4], 0x55u);
  expect_u64("offset-disjoint first public byte", control_buffer[8], 0x66u);
  expect_u64("offset-disjoint second secret",
             offset_disjoint_control(control_buffer, 0x77u, 0x66u), 0x66u);
  expect_u64("offset-disjoint second stored secret", control_buffer[4], 0x77u);
  expect_u64("offset-disjoint second public byte", control_buffer[8], 0x66u);

  expect_u64("offset-overlap first witness",
             offset_overlap_bad(bad_buffer, 0x55u, 0x66u), 0x55u);
  expect_u64("offset-overlap first stored secret", bad_buffer[4], 0x55u);
  expect_u64("offset-overlap first public byte", bad_buffer[8], 0x66u);
  expect_u64("offset-overlap second witness",
             offset_overlap_bad(bad_buffer, 0x77u, 0x66u), 0x77u);
  expect_u64("offset-overlap second stored secret", bad_buffer[4], 0x77u);
  expect_u64("offset-overlap second public byte", bad_buffer[8], 0x66u);
}

static void check_pointer_rebinding(void) {
  uint8_t left = 0x21u;
  uint8_t right = 0xa4u;
  uint8_t selected_left = 0u;
  uint8_t selected_right = 0u;
  uint8_t shared = 0xc3u;

  /* Distinct bytes show that both selector directions preserve behavior. */
  pointer_rebinding_disjoint_select_bad(0u, &left, &right, &selected_left);
  pointer_rebinding_disjoint_select_bad(1u, &left, &right, &selected_right);
  expect_u64("pointer rebinding disjoint false", selected_left, left);
  expect_u64("pointer rebinding disjoint true", selected_right, right);

  /* Equal bytes isolate the allocation-class difference from output values. */
  left = 0x5au;
  right = 0x5au;
  selected_left = 0u;
  selected_right = 0u;
  pointer_rebinding_disjoint_select_bad(0u, &left, &right, &selected_left);
  pointer_rebinding_disjoint_select_bad(1u, &left, &right, &selected_right);
  expect_u64("pointer rebinding isolated false", selected_left, 0x5au);
  expect_u64("pointer rebinding isolated true", selected_right, 0x5au);
  expect_u64("pointer rebinding isolated equal output", selected_left,
             selected_right);

  /* The precision control realizes both root views with one actual pointer. */
  selected_left = 0u;
  selected_right = 0u;
  pointer_rebinding_same_allocation_control(0u, &shared, &shared,
                                            &selected_left);
  pointer_rebinding_same_allocation_control(1u, &shared, &shared,
                                            &selected_right);
  expect_u64("pointer rebinding same actual false", selected_left, shared);
  expect_u64("pointer rebinding same actual true", selected_right, shared);
  expect_u64("pointer rebinding same actual equal output", selected_left,
             selected_right);

  /* Exercise both selector values even though the checked shape is refused. */
  left = 0x36u;
  right = 0x9du;
  selected_left = 0u;
  selected_right = 0u;
  pointer_rebinding_pointer_spill_unsupported(0u, &left, &right,
                                              &selected_left);
  pointer_rebinding_pointer_spill_unsupported(1u, &left, &right,
                                              &selected_right);
  expect_u64("pointer spill false", selected_left, left);
  expect_u64("pointer spill true", selected_right, right);
}

static void check_remaining_models(void) {
  unsigned p = 0u, q = 0u, out = 0u;
  uint8_t public_byte = 0xffu;
  uint32_t carrier[2] = {0};
  uint64_t pointed = 0xfedcba9876543210ull;
  const uint64_t fallback = 0x0123456789abcdefull;
  int32_t logits[10] = {0};

  abi_alias_missing_binding(0x1234u, &p, &p, &out);
  expect_u64("ABI missing-binding body overlap behavior", out, 0x1234u);
  abi_alias_mayalias_overlap(0x5678u, &p, &p, &out);
  expect_u64("ABI may-alias overlap witness", out, 0x5678u);
  abi_alias_explicit_same_actual(0x9abcu, &p, &out);
  expect_u64("ABI explicit same-actual witness", out, 0x9abcu);
  q = 0x9abcu;
  abi_alias_disjoint_control(0xdef0u, &p, &q, &out);
  expect_u64("ABI disjoint public reload", out, 0x9abcu);

  out = 1u;
  alloca_size_high_count(0, &out);
  expect_u64("high VLA public sink, false arm", out, 0u);
  out = 1u;
  alloca_size_high_count(1, &out);
  expect_u64("high VLA public sink, true arm", out, 0u);
  out = 1u;
  alloca_size_public_control(64u, &out);
  expect_u64("public VLA public sink", out, 0u);
  alloca_size_fixed_region_copy_bad(0u, &public_byte);
  expect_u64("fixed array left witness", public_byte, 0u);
  alloca_size_fixed_region_copy_bad(1u, &public_byte);
  expect_u64("fixed array right witness", public_byte, 1u);

  for (unsigned i = 0; i < 10; ++i)
    logits[i] = -100;
  logits[4] = -1;
  expect_u64("argmax all-negative maximum", argmax_release_body(logits), 4u);
  for (unsigned i = 0; i < 10; ++i)
    logits[i] = 0;
  expect_u64("argmax lowest-index tie", argmax_release_body(logits), 0u);
  logits[2] = 7;
  logits[7] = 7;
  expect_u64("argmax strict tie rule", argmax_release_body(logits), 2u);
  logits[7] = 8;
  expect_u64("argmax later maximum", argmax_release_body(logits), 7u);

  audience_mismatch_bad(0x1234u);
  expect_u64("audience authorized payload", transfer_audience_alice, 0x34u);
  expect_u64("audience unauthorized payload", transfer_audience_bob, 0x34u);

  audience_mismatch_authorized(0x1234u);
  expect_u64("two-member audience Alice payload", transfer_authorized_alice,
             0x34u);
  expect_u64("two-member audience Bob payload", transfer_authorized_bob,
             0x34u);
  audience_joint_authorized(0x1234u);
  expect_u64("joint audience payload", transfer_joint_endpoint, 0x34u);
  audience_joint_singleton_visible_bad(0x1234u);
  expect_u64("joint audience singleton witness", transfer_joint_to_alice,
             0x34u);
  audience_unauthorized_concealed(0x1234u);
  expect_u64("concealed audience payload", transfer_concealed_endpoint,
             0x34u);
  audience_location_visible_bad(0x1234u);
  audience_world_authorized(0x1234u);
  expect_u64("world audience payload", transfer_world_endpoint, 0x34u);
  audience_equal_release_then_leak_bad(0x1234u);
  expect_u64("equal release later leak witness", transfer_equal_release_observer,
             0x1234u);

  out = 1u;
  bound_secret_trip_count_bad(0, &out);
  expect_u64("secret trip count zero", out, 0u);
  out = 1u;
  bound_secret_trip_count_bad(3, &out);
  expect_u64("secret trip count backedge", out, 0u);
  out = 1u;
  bound_exhausted_public_loop(3, &out);
  expect_u64("public bound backedge", out, 0u);
  out = 1u;
  bound_adequate_public_loop(8, &out);
  expect_u64("adequate public bound", out, 0u);

  expect_u64("launder ternary false", launder_scan_bad(0, fallback, &pointed),
             fallback);
  expect_u64("launder ternary true", launder_scan_bad(1, fallback, &pointed),
             pointed);
  expect_u64("launder folded mask false",
             launder_scan_folded_bad(0, fallback, &pointed), fallback);
  expect_u64("launder folded mask true",
             launder_scan_folded_bad(1, fallback, &pointed), pointed);
  expect_u64("launder barrier false",
             launder_scan_fixed(0, fallback, &pointed), fallback);
  expect_u64("launder barrier true",
             launder_scan_fixed(1, fallback, &pointed), pointed);

  expect_u64("predecessor false", predecessor_choice_blockarg_bad(0), 20u);
  expect_u64("predecessor true", predecessor_choice_blockarg_bad(1), 10u);

  prefix_causal_release_bad(0x4567u);
  expect_u64("prefix-causal early observation", transfer_prefix_public,
             0x4567u);

  expect_u64("release wrapper", sps_release_invalid_callable(0xf3u, 0x3cu), 0x30u);
  release_carrier(0xf3u, 0x0fu, 0xf0u, carrier);
  expect_u64("release carrier first occurrence", carrier[0], 0x03u);
  expect_u64("release carrier second occurrence", carrier[1], 0xf0u);

  expect_u64("SHA-256 round reduction",
             sha256_round_release_body(0x510e527fu, 0x9b05688cu,
                                       0x1f83d9abu, 0x5be0cd19u,
                                       0x428a2f98u, 0x61626380u),
             0x54da50e8u);
}

int main(void) {
  check_clangover();
  check_kyberslash();
  check_wolfssl();
  check_semantic_harnesses();
  check_precision_controls();
  check_pointer_rebinding();
  check_remaining_models();

  if (failures != 0)
    return 1;
  return 0;
}
