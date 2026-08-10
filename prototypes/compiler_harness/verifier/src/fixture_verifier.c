#include "internal.h"

#include <stdlib.h>
#include <string.h>

sps_fixture_status sps_fixture_derive_trace(const uint8_t *trace_bytes,
                                            size_t trace_size,
                                            sps_fixture_actual **out_actual) {
  sps_fixture_actual *actual;
  spsv_parse_error error;
  int parsed;
  if ((!trace_bytes && trace_size != 0) || !out_actual)
    return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  *out_actual = NULL;
  actual = (sps_fixture_actual *)calloc(1, sizeof(*actual));
  if (!actual) return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
  actual->state = SPS_FIXTURE_ACTUAL_INVALID;
  actual->view.state = SPS_FIXTURE_ACTUAL_INVALID;
  actual->view.authority = SPS_FIXTURE_AUTHORITY_TEST_ONLY;
  actual->view.sps_model_status = SPS_FIXTURE_MODEL_STATUS_NOT_COMPUTED;
  actual->view.sensitivity = SPS_FIXTURE_SENSITIVITY_RESTRICTED;
  memset(&error, 0, sizeof(error));
  parsed = spsv_parse_yaml(trace_bytes, trace_size, &actual->root, &error);
  if (parsed < 0) {
    free(error.message);
    sps_fixture_actual_destroy(actual);
    return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
  }
  if (!parsed) {
    if (!spsv_add_actual_issue(
            actual, SPS_FIXTURE_ISSUE_INVALID_INPUT,
            SPS_FIXTURE_PHASE_TRACE_PARSE, "InvalidYaml", "",
            error.message ? error.message : "invalid YAML", &error.location)) {
      free(error.message);
      sps_fixture_actual_destroy(actual);
      return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
    }
    free(error.message);
    *out_actual = actual;
    return SPS_FIXTURE_STATUS_OK;
  }
  if (!spsv_validate_and_derive_trace(actual)) {
    if (actual->out_of_memory || actual->issue_count == 0) {
      sps_fixture_actual_destroy(actual);
      return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
    }
    *out_actual = actual;
    return SPS_FIXTURE_STATUS_OK;
  }
  actual->state = SPS_FIXTURE_ACTUAL_DERIVED;
  actual->view.state = SPS_FIXTURE_ACTUAL_DERIVED;
  *out_actual = actual;
  return SPS_FIXTURE_STATUS_OK;
}

sps_fixture_status sps_fixture_compare_snapshot(
    const sps_fixture_actual *actual, const uint8_t *snapshot_bytes,
    size_t snapshot_size, sps_fixture_result **out_result) {
  sps_fixture_result *result;
  spsv_parse_error error;
  int parsed;
  if (!actual || (!snapshot_bytes && snapshot_size != 0) || !out_result)
    return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  *out_result = NULL;
  result = (sps_fixture_result *)calloc(1, sizeof(*result));
  if (!result) return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
  result->view.comparison = SPS_FIXTURE_COMPARISON_INVALID;
  result->view.authority = SPS_FIXTURE_AUTHORITY_TEST_ONLY;
  result->view.sps_model_status = SPS_FIXTURE_MODEL_STATUS_NOT_COMPUTED;
  result->view.sensitivity = SPS_FIXTURE_SENSITIVITY_RESTRICTED;
  result->view.sensitivity = actual->view.sensitivity;
  if (actual->state != SPS_FIXTURE_ACTUAL_DERIVED) {
    size_t i;
    for (i = 0; i < actual->issue_count; ++i) {
      const spsv_issue *issue = &actual->issues[i];
      if (!spsv_add_result_issue(
              result, issue->kind, issue->phase, issue->code, issue->path,
              issue->message,
              issue->location.present ? &issue->location : NULL)) {
        sps_fixture_result_destroy(result);
        return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
      }
    }
    if (!spsv_add_result_issue(
            result, SPS_FIXTURE_ISSUE_INVALID_INPUT,
            SPS_FIXTURE_PHASE_COMPARE, "InvalidActual", "",
            "snapshot comparison requires a successfully derived trace", NULL)) {
      sps_fixture_result_destroy(result);
      return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
    }
    *out_result = result;
    return SPS_FIXTURE_STATUS_OK;
  }
  memset(&error, 0, sizeof(error));
  parsed =
      spsv_parse_yaml(snapshot_bytes, snapshot_size, &result->snapshot_root,
                      &error);
  if (parsed < 0) {
    free(error.message);
    sps_fixture_result_destroy(result);
    return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
  }
  if (!parsed) {
    if (!spsv_add_result_issue(
            result, SPS_FIXTURE_ISSUE_INVALID_INPUT,
            SPS_FIXTURE_PHASE_SNAPSHOT_PARSE, "InvalidYaml", "",
            error.message ? error.message : "invalid YAML", &error.location)) {
      free(error.message);
      sps_fixture_result_destroy(result);
      return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
    }
    free(error.message);
    *out_result = result;
    return SPS_FIXTURE_STATUS_OK;
  }
  result->view.comparison = SPS_FIXTURE_COMPARISON_MATCHED;
  if (!spsv_validate_and_compare_snapshot(result, actual)) {
    if (result->out_of_memory || result->issue_count == 0) {
      sps_fixture_result_destroy(result);
      return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
    }
    result->view.comparison = SPS_FIXTURE_COMPARISON_INVALID;
  }
  *out_result = result;
  return SPS_FIXTURE_STATUS_OK;
}

sps_fixture_status sps_fixture_result_write_json(
    const sps_fixture_result *result, char *destination, size_t capacity,
    size_t *required_size) {
  char *rendered;
  size_t size;
  if (!result || !required_size) return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  if (!spsv_render_result_json(result, &rendered, &size))
    return SPS_FIXTURE_STATUS_OUT_OF_MEMORY;
  *required_size = size;
  if (!destination || capacity < size) {
    free(rendered);
    return size == 0 ? SPS_FIXTURE_STATUS_OK
                     : SPS_FIXTURE_STATUS_BUFFER_TOO_SMALL;
  }
  memcpy(destination, rendered, size);
  free(rendered);
  return SPS_FIXTURE_STATUS_OK;
}
