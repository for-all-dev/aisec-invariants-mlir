#ifndef SPS_FIXTURE_VERIFIER_INTERNAL_H
#define SPS_FIXTURE_VERIFIER_INTERNAL_H

#include "sps_harness/fixture_verifier.h"

#include <stddef.h>
#include <stdint.h>

typedef enum {
  SPSV_NODE_STRING,
  SPSV_NODE_BOOL,
  SPSV_NODE_INTEGER,
  SPSV_NODE_SEQUENCE,
  SPSV_NODE_MAPPING
} spsv_node_kind;

typedef struct spsv_node spsv_node;

typedef struct {
  char *key;
  spsv_node *value;
} spsv_pair;

struct spsv_node {
  spsv_node_kind kind;
  sps_fixture_source_location location;
  union {
    char *string;
    int boolean;
    int64_t integer;
    struct {
      spsv_node **items;
      size_t count;
      size_t capacity;
    } sequence;
    struct {
      spsv_pair *items;
      size_t count;
      size_t capacity;
    } mapping;
  } as;
};

typedef struct {
  char *message;
  sps_fixture_source_location location;
} spsv_parse_error;

typedef struct {
  sps_fixture_issue_kind kind;
  sps_fixture_issue_phase phase;
  char *code;
  char *path;
  char *message;
  sps_fixture_source_location location;
} spsv_issue;

typedef struct {
  char *expectation_path;
  char *actual_path;
  sps_fixture_check_kind check;
  sps_fixture_consumption_disposition disposition;
  char *expected_json;
  char *actual_json;
} spsv_consumption;

typedef struct {
  char *pipeline;
  sps_fixture_comparison comparison;
} spsv_pipeline;

struct sps_fixture_actual {
  sps_fixture_actual_state state;
  sps_fixture_actual_view view;
  spsv_node *root;
  spsv_node *captures;
  spsv_node *event_coverage;
  char *derived_reason;
  spsv_issue *issues;
  size_t issue_count;
  size_t issue_capacity;
  int out_of_memory;
};

struct sps_fixture_result {
  sps_fixture_result_view view;
  spsv_node *snapshot_root;
  char *case_id;
  char *entry;
  char *deployment;
  char *policy;
  char *cause;
  char *reason;
  char *first_kind;
  char *first_field;
  char *first_id;
  spsv_pipeline *pipelines;
  size_t pipeline_count;
  size_t pipeline_capacity;
  spsv_consumption *consumptions;
  size_t consumption_count;
  size_t consumption_capacity;
  spsv_issue *issues;
  size_t issue_count;
  size_t issue_capacity;
  int out_of_memory;
};

int spsv_parse_yaml(const uint8_t *bytes, size_t size, spsv_node **out_root,
                    spsv_parse_error *out_error);
void spsv_node_destroy(spsv_node *node);
const spsv_node *spsv_map_get(const spsv_node *map, const char *key);
int spsv_map_has_only(const spsv_node *map, const char *const *keys,
                      size_t key_count, const char **out_bad_key);
int spsv_node_equal(const spsv_node *left, const spsv_node *right);
char *spsv_node_json(const spsv_node *node);
char *spsv_strdup(const char *value);
char *spsv_path_join(const char *left, const char *right);
int spsv_is_sha256(const spsv_node *node);
int spsv_case_id_valid(const char *value);
int spsv_mlir_symbol_valid(const char *value);
int spsv_stable_id_valid(const char *value);
int spsv_pipeline_id_valid(const char *value);
int spsv_fact_key_valid(const char *value);
int spsv_pipeline_kind_valid(const char *value);
int spsv_event_pair_valid(const char *kind, const char *field);
int spsv_policy_valid(const char *value);
int spsv_facts_expectation_blind(const spsv_node *node);
size_t spsv_utf8_length(const char *value);

int spsv_add_actual_issue(sps_fixture_actual *actual,
                          sps_fixture_issue_kind kind,
                          sps_fixture_issue_phase phase, const char *code,
                          const char *path, const char *message,
                          const sps_fixture_source_location *location);
int spsv_add_result_issue(sps_fixture_result *result,
                          sps_fixture_issue_kind kind,
                          sps_fixture_issue_phase phase, const char *code,
                          const char *path, const char *message,
                          const sps_fixture_source_location *location);
int spsv_add_consumption(sps_fixture_result *result, const char *expected_path,
                         const char *actual_path, sps_fixture_check_kind check,
                         int matched, const spsv_node *expected,
                         const spsv_node *actual);
int spsv_add_consumption_strings(
    sps_fixture_result *result, const char *expected_path,
    const char *actual_path, sps_fixture_check_kind check, int matched,
    const char *expected, const char *actual);
int spsv_add_ignored(sps_fixture_result *result, const char *path);
int spsv_add_pipeline(sps_fixture_result *result, const char *id,
                      sps_fixture_comparison comparison);

int spsv_validate_and_derive_trace(sps_fixture_actual *actual);
int spsv_validate_and_compare_snapshot(sps_fixture_result *result,
                                       const sps_fixture_actual *actual);
int spsv_render_result_json(const sps_fixture_result *result, char **out,
                            size_t *out_size);

sps_fixture_text_view spsv_text_view(const char *text);
sps_fixture_issue_view spsv_issue_view(const spsv_issue *issue);

#endif
