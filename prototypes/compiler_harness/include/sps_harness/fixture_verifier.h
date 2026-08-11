#ifndef SPS_HARNESS_FIXTURE_VERIFIER_H
#define SPS_HARNESS_FIXTURE_VERIFIER_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct sps_fixture_actual sps_fixture_actual;
typedef struct sps_fixture_result sps_fixture_result;

/*
 * Inputs are borrowed only for the duration of each call. Handles own all
 * retained data and are immutable after construction. Every text view is
 * borrowed from its owning handle, is not necessarily NUL-terminated, and
 * remains valid until that handle is destroyed. Destroy functions accept NULL.
 * Handles support concurrent read-only access; no global initialization exists.
 */
typedef struct {
  const char *data;
  size_t size;
} sps_fixture_text_view;

typedef enum {
  SPS_FIXTURE_STATUS_OK = 0,
  SPS_FIXTURE_STATUS_INVALID_ARGUMENT,
  SPS_FIXTURE_STATUS_OUT_OF_MEMORY,
  SPS_FIXTURE_STATUS_BUFFER_TOO_SMALL,
  SPS_FIXTURE_STATUS_OUT_OF_RANGE
} sps_fixture_status;

typedef enum {
  SPS_FIXTURE_ACTUAL_INVALID = 0,
  SPS_FIXTURE_ACTUAL_DERIVED
} sps_fixture_actual_state;

typedef enum {
  SPS_FIXTURE_COMPARISON_INVALID = 0,
  SPS_FIXTURE_COMPARISON_MATCHED,
  SPS_FIXTURE_COMPARISON_MISMATCHED
} sps_fixture_comparison;

typedef enum { SPS_FIXTURE_AUTHORITY_TEST_ONLY = 1 } sps_fixture_authority;
typedef enum { SPS_FIXTURE_MODEL_STATUS_NOT_COMPUTED = 0 } sps_fixture_model_status;
typedef enum {
  SPS_FIXTURE_SENSITIVITY_SYNTHETIC_TEST_DATA = 0,
  SPS_FIXTURE_SENSITIVITY_RESTRICTED
} sps_fixture_sensitivity;

typedef enum {
  SPS_FIXTURE_POSITION_NONE = 0,
  SPS_FIXTURE_POSITION_PROVED,
  SPS_FIXTURE_POSITION_COUNTEREXAMPLE,
  SPS_FIXTURE_POSITION_UNKNOWN
} sps_fixture_position_tag;

typedef struct {
  sps_fixture_text_view kind;
  sps_fixture_text_view field;
  sps_fixture_text_view id;
} sps_fixture_event_view;

typedef struct {
  sps_fixture_position_tag tag;
  sps_fixture_text_view deployment;
  sps_fixture_text_view policy;
  union {
    struct {
      sps_fixture_text_view cause;
      sps_fixture_event_view first_difference;
    } counterexample;
    struct { sps_fixture_text_view reason; } unknown;
  } detail;
} sps_fixture_position_view;

typedef enum {
  SPS_FIXTURE_PHASE_TRACE_PARSE = 0,
  SPS_FIXTURE_PHASE_TRACE_VALIDATE,
  SPS_FIXTURE_PHASE_TRACE_DERIVE,
  SPS_FIXTURE_PHASE_SNAPSHOT_PARSE,
  SPS_FIXTURE_PHASE_SNAPSHOT_VALIDATE,
  SPS_FIXTURE_PHASE_COMPARE
} sps_fixture_issue_phase;

typedef enum {
  SPS_FIXTURE_ISSUE_INVALID_INPUT = 0,
  SPS_FIXTURE_ISSUE_EXPECTATION_MISMATCH
} sps_fixture_issue_kind;

typedef struct {
  uint8_t present;
  size_t byte_offset; /* Zero-based UTF-8 byte offset. */
  size_t line;        /* One-based source line. */
  size_t column;      /* One-based source column reported by libyaml. */
} sps_fixture_source_location;

typedef struct {
  sps_fixture_issue_kind kind;
  sps_fixture_issue_phase phase;
  sps_fixture_text_view code;
  sps_fixture_text_view path;
  sps_fixture_text_view message;
  sps_fixture_source_location location;
} sps_fixture_issue_view;

typedef enum {
  SPS_FIXTURE_CHECK_EXACT = 0,
  SPS_FIXTURE_CHECK_EQUALS,
  SPS_FIXTURE_CHECK_CONTAINS,
  SPS_FIXTURE_CHECK_EXCLUDES,
  SPS_FIXTURE_CHECK_COUNT_EQ,
  SPS_FIXTURE_CHECK_COUNT_MIN,
  SPS_FIXTURE_CHECK_COUNT_MAX,
  SPS_FIXTURE_CHECK_ORDERED,
  SPS_FIXTURE_CHECK_IGNORED_EXPLANATION
} sps_fixture_check_kind;

typedef enum {
  SPS_FIXTURE_CONSUMED_MATCHED = 0,
  SPS_FIXTURE_CONSUMED_MISMATCHED,
  SPS_FIXTURE_CONSUMED_IGNORED
} sps_fixture_consumption_disposition;

typedef struct {
  sps_fixture_text_view expectation_path;
  sps_fixture_text_view actual_path;
  sps_fixture_check_kind check;
  sps_fixture_consumption_disposition disposition;
  sps_fixture_text_view expected_json;
  sps_fixture_text_view actual_json;
} sps_fixture_consumption_view;

typedef struct {
  sps_fixture_text_view pipeline;
  sps_fixture_comparison comparison;
} sps_fixture_pipeline_view;

typedef struct {
  sps_fixture_actual_state state;
  sps_fixture_authority authority;
  sps_fixture_model_status sps_model_status;
  sps_fixture_sensitivity sensitivity;
  sps_fixture_text_view case_id;
  sps_fixture_text_view entry;
  sps_fixture_position_view position;
} sps_fixture_actual_view;

typedef struct {
  sps_fixture_comparison comparison;
  sps_fixture_authority authority;
  sps_fixture_model_status sps_model_status;
  sps_fixture_sensitivity sensitivity;
  sps_fixture_text_view case_id;
  sps_fixture_text_view entry;
  sps_fixture_position_view position;
} sps_fixture_result_view;

/*
 * Status values report API/operational success, not fixture validity.
 * Malformed or inconsistent wire input returns STATUS_OK with an
 * ACTUAL_INVALID handle; inspect the view and issues. This keeps validation
 * diagnostics deterministic and serializable. A byte pointer may be NULL only
 * when its size is zero; an empty span is malformed wire, not an API error.
 */
sps_fixture_status sps_fixture_derive_trace(const uint8_t *trace_bytes,
                                            size_t trace_size,
                                            sps_fixture_actual **out_actual);
void sps_fixture_actual_destroy(sps_fixture_actual *actual);
sps_fixture_status sps_fixture_actual_get_view(const sps_fixture_actual *actual,
                                               sps_fixture_actual_view *out_view);
size_t sps_fixture_actual_issue_count(const sps_fixture_actual *actual);
sps_fixture_status sps_fixture_actual_issue_at(const sps_fixture_actual *actual,
                                               size_t index,
                                               sps_fixture_issue_view *out_issue);
size_t sps_fixture_actual_event_count(const sps_fixture_actual *actual);
sps_fixture_status sps_fixture_actual_event_at(const sps_fixture_actual *actual,
                                               size_t index,
                                               sps_fixture_event_view *out_event);

/*
 * Likewise, STATUS_OK may carry COMPARISON_INVALID or MISMATCHED. Only the
 * result view's comparison field determines the test-contract outcome. The
 * snapshot pointer follows the same NULL-if-and-only-if-size-zero rule.
 */
sps_fixture_status sps_fixture_compare_snapshot(const sps_fixture_actual *actual,
                                                const uint8_t *snapshot_bytes,
                                                size_t snapshot_size,
                                                sps_fixture_result **out_result);
void sps_fixture_result_destroy(sps_fixture_result *result);
sps_fixture_status sps_fixture_result_get_view(const sps_fixture_result *result,
                                               sps_fixture_result_view *out_view);
size_t sps_fixture_result_issue_count(const sps_fixture_result *result);
sps_fixture_status sps_fixture_result_issue_at(const sps_fixture_result *result,
                                               size_t index,
                                               sps_fixture_issue_view *out_issue);
size_t sps_fixture_result_pipeline_count(const sps_fixture_result *result);
sps_fixture_status sps_fixture_result_pipeline_at(
    const sps_fixture_result *result, size_t index,
    sps_fixture_pipeline_view *out_pipeline);
size_t sps_fixture_result_consumption_count(const sps_fixture_result *result);
sps_fixture_status sps_fixture_result_consumption_at(
    const sps_fixture_result *result, size_t index,
    sps_fixture_consumption_view *out_consumption);
/*
 * The consumption ledger includes explanation-only rows with disposition
 * SPS_FIXTURE_CONSUMED_IGNORED. Their expected_json and actual_json views are
 * empty/undefined; JSON projects those rows into "ignored".
 *
 * required_size excludes a trailing NUL. The writer emits exactly that many
 * UTF-8 bytes and never writes a NUL terminator. Passing a null destination
 * with zero capacity is a size query and returns BUFFER_TOO_SMALL for nonempty
 * output.
 */
sps_fixture_status sps_fixture_result_write_json(const sps_fixture_result *result,
                                                 char *destination,
                                                 size_t capacity,
                                                 size_t *required_size);

#ifdef __cplusplus
}
#endif

#endif
