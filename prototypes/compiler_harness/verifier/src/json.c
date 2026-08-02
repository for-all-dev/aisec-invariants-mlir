#include "internal.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  char *data;
  size_t size;
  size_t capacity;
  int failed;
} spsv_json_buffer;

static void spsv_jgrow(spsv_json_buffer *b, size_t add) {
  char *grown;
  size_t capacity;
  if (b->failed || add > SIZE_MAX - b->size - 1) {
    b->failed = 1;
    return;
  }
  if (b->size + add + 1 <= b->capacity) return;
  capacity = b->capacity ? b->capacity : 512;
  while (capacity < b->size + add + 1) {
    if (capacity > SIZE_MAX / 2) {
      b->failed = 1;
      return;
    }
    capacity *= 2;
  }
  grown = (char *)realloc(b->data, capacity);
  if (!grown) {
    b->failed = 1;
    return;
  }
  b->data = grown;
  b->capacity = capacity;
}

static void spsv_jraw(spsv_json_buffer *b, const char *text) {
  if (!text) {
    b->failed = 1;
    return;
  }
  size_t n = strlen(text);
  spsv_jgrow(b, n);
  if (b->failed) return;
  memcpy(b->data + b->size, text, n);
  b->size += n;
  b->data[b->size] = '\0';
}

static void spsv_jstring(spsv_json_buffer *b, const char *text) {
  const unsigned char *p = (const unsigned char *)(text ? text : "");
  char tmp[8];
  spsv_jraw(b, "\"");
  while (*p) {
    if (*p == '"' || *p == '\\') {
      tmp[0] = '\\';
      tmp[1] = (char)*p;
      tmp[2] = '\0';
      spsv_jraw(b, tmp);
    } else if (*p < 0x20) {
      (void)snprintf(tmp, sizeof(tmp), "\\u%04x", *p);
      spsv_jraw(b, tmp);
    } else {
      tmp[0] = (char)*p;
      tmp[1] = '\0';
      spsv_jraw(b, tmp);
    }
    ++p;
  }
  spsv_jraw(b, "\"");
}

static const char *spsv_comparison_name(sps_fixture_comparison value) {
  switch (value) {
  case SPS_FIXTURE_COMPARISON_MATCHED:
    return "Matched";
  case SPS_FIXTURE_COMPARISON_MISMATCHED:
    return "Mismatched";
  case SPS_FIXTURE_COMPARISON_INVALID:
    return "Invalid";
  }
  return "Invalid";
}

static const char *spsv_position_name(sps_fixture_position_tag value) {
  switch (value) {
  case SPS_FIXTURE_POSITION_PROVED:
    return "Proved";
  case SPS_FIXTURE_POSITION_COUNTEREXAMPLE:
    return "Counterexample";
  case SPS_FIXTURE_POSITION_UNKNOWN:
    return "Unknown";
  case SPS_FIXTURE_POSITION_NONE:
    return "None";
  }
  return "None";
}

static const char *spsv_check_name(sps_fixture_check_kind value) {
  switch (value) {
  case SPS_FIXTURE_CHECK_EXACT:
    return "Exact";
  case SPS_FIXTURE_CHECK_EQUALS:
    return "Equals";
  case SPS_FIXTURE_CHECK_CONTAINS:
    return "Contains";
  case SPS_FIXTURE_CHECK_EXCLUDES:
    return "Excludes";
  case SPS_FIXTURE_CHECK_COUNT_EQ:
    return "CountEq";
  case SPS_FIXTURE_CHECK_COUNT_MIN:
    return "CountMin";
  case SPS_FIXTURE_CHECK_COUNT_MAX:
    return "CountMax";
  case SPS_FIXTURE_CHECK_ORDERED:
    return "Ordered";
  case SPS_FIXTURE_CHECK_IGNORED_EXPLANATION:
    return "IgnoredExplanation";
  }
  return "Exact";
}

static const char *spsv_disposition_name(
    sps_fixture_consumption_disposition value) {
  switch (value) {
  case SPS_FIXTURE_CONSUMED_MATCHED:
    return "Matched";
  case SPS_FIXTURE_CONSUMED_MISMATCHED:
    return "Mismatched";
  case SPS_FIXTURE_CONSUMED_IGNORED:
    return "Ignored";
  }
  return "Mismatched";
}

static const char *spsv_issue_kind_name(sps_fixture_issue_kind value) {
  return value == SPS_FIXTURE_ISSUE_EXPECTATION_MISMATCH
             ? "ExpectationMismatch"
             : "InvalidInput";
}

static const char *spsv_phase_name(sps_fixture_issue_phase value) {
  switch (value) {
  case SPS_FIXTURE_PHASE_TRACE_PARSE:
    return "TraceParse";
  case SPS_FIXTURE_PHASE_TRACE_VALIDATE:
    return "TraceValidate";
  case SPS_FIXTURE_PHASE_TRACE_DERIVE:
    return "TraceDerive";
  case SPS_FIXTURE_PHASE_SNAPSHOT_PARSE:
    return "SnapshotParse";
  case SPS_FIXTURE_PHASE_SNAPSHOT_VALIDATE:
    return "SnapshotValidate";
  case SPS_FIXTURE_PHASE_COMPARE:
    return "Compare";
  }
  return "Compare";
}

static const char *spsv_sensitivity_name(sps_fixture_sensitivity value) {
  return value == SPS_FIXTURE_SENSITIVITY_RESTRICTED ? "Restricted"
                                                     : "SyntheticTestData";
}

static void spsv_render_event(spsv_json_buffer *b, const char *kind,
                              const char *field, const char *id) {
  spsv_jraw(b, "{\"kind\":");
  spsv_jstring(b, kind);
  spsv_jraw(b, ",\"field\":");
  spsv_jstring(b, field);
  if (id && id[0]) {
    spsv_jraw(b, ",\"id\":");
    spsv_jstring(b, id);
  }
  spsv_jraw(b, "}");
}

static void spsv_render_position(spsv_json_buffer *b,
                                 const sps_fixture_result *result) {
  spsv_jraw(b, "{\"tag\":");
  spsv_jstring(b, spsv_position_name(result->view.position.tag));
  if (result->view.position.tag == SPS_FIXTURE_POSITION_COUNTEREXAMPLE) {
    spsv_jraw(b, ",\"cause\":");
    spsv_jstring(b, result->cause);
    spsv_jraw(b, ",\"first_difference\":");
    spsv_render_event(b, result->first_kind, result->first_field,
                      result->first_id);
  } else if (result->view.position.tag == SPS_FIXTURE_POSITION_UNKNOWN) {
    spsv_jraw(b, ",\"reason\":");
    spsv_jstring(b, result->reason);
  }
  spsv_jraw(b, "}");
}

int spsv_render_result_json(const sps_fixture_result *result, char **out,
                            size_t *out_size) {
  spsv_json_buffer b;
  size_t i;
  int first;
  memset(&b, 0, sizeof(b));
  *out = NULL;
  *out_size = 0;
  spsv_jraw(&b,
            "{\"format\":\"SPS-Harness-Verification-Result\","
            "\"authority\":\"TestOnly\",\"claimable\":false,"
            "\"sps_model_status\":\"NotComputed\",\"sensitivity\":");
  spsv_jstring(&b, spsv_sensitivity_name(result->view.sensitivity));
  spsv_jraw(&b, ",\"outcome\":{\"tag\":");
  spsv_jstring(&b, spsv_comparison_name(result->view.comparison));
  if (result->case_id && result->case_id[0]) {
    spsv_jraw(&b, ",\"case\":");
    spsv_jstring(&b, result->case_id);
  }
  if (result->entry && result->entry[0]) {
    spsv_jraw(&b, ",\"entry\":");
    spsv_jstring(&b, result->entry);
  }
  if (result->view.comparison != SPS_FIXTURE_COMPARISON_INVALID) {
    spsv_jraw(&b, ",\"actual\":{\"position\":");
    spsv_render_position(&b, result);
    spsv_jraw(&b, ",\"deployment\":");
    spsv_jstring(&b, result->deployment);
    spsv_jraw(&b, ",\"policy\":");
    spsv_jstring(&b, result->policy);
    spsv_jraw(&b, "}");
  }
  spsv_jraw(&b, "},\"pipelines\":[");
  for (i = 0; i < result->pipeline_count; ++i) {
    if (i) spsv_jraw(&b, ",");
    spsv_jraw(&b, "{\"pipeline\":");
    spsv_jstring(&b, result->pipelines[i].pipeline);
    spsv_jraw(&b, ",\"comparison\":");
    spsv_jstring(&b,
                  spsv_comparison_name(result->pipelines[i].comparison));
    spsv_jraw(&b, "}");
  }
  spsv_jraw(&b, "],\"consumed\":[");
  first = 1;
  for (i = 0; i < result->consumption_count; ++i) {
    const spsv_consumption *row = &result->consumptions[i];
    if (row->disposition == SPS_FIXTURE_CONSUMED_IGNORED) continue;
    if (!first) spsv_jraw(&b, ",");
    first = 0;
    spsv_jraw(&b, "{\"expectation_path\":");
    spsv_jstring(&b, row->expectation_path);
    spsv_jraw(&b, ",\"actual_path\":");
    spsv_jstring(&b, row->actual_path);
    spsv_jraw(&b, ",\"check\":");
    spsv_jstring(&b, spsv_check_name(row->check));
    spsv_jraw(&b, ",\"disposition\":");
    spsv_jstring(&b, spsv_disposition_name(row->disposition));
    spsv_jraw(&b, ",\"expected\":");
    spsv_jraw(&b, row->expected_json);
    spsv_jraw(&b, ",\"actual\":");
    spsv_jraw(&b, row->actual_json);
    spsv_jraw(&b, "}");
  }
  spsv_jraw(&b, "],\"ignored\":[");
  first = 1;
  for (i = 0; i < result->consumption_count; ++i) {
    const spsv_consumption *row = &result->consumptions[i];
    if (row->disposition != SPS_FIXTURE_CONSUMED_IGNORED) continue;
    if (!first) spsv_jraw(&b, ",");
    first = 0;
    spsv_jraw(&b, "{\"path\":");
    spsv_jstring(&b, row->expectation_path);
    spsv_jraw(&b, ",\"reason\":\"ExplanationOnly\"}");
  }
  spsv_jraw(&b, "],\"issues\":[");
  for (i = 0; i < result->issue_count; ++i) {
    const spsv_issue *issue = &result->issues[i];
    if (i) spsv_jraw(&b, ",");
    spsv_jraw(&b, "{\"kind\":");
    spsv_jstring(&b, spsv_issue_kind_name(issue->kind));
    spsv_jraw(&b, ",\"phase\":");
    spsv_jstring(&b, spsv_phase_name(issue->phase));
    spsv_jraw(&b, ",\"code\":");
    spsv_jstring(&b, issue->code);
    spsv_jraw(&b, ",\"path\":");
    spsv_jstring(&b, issue->path);
    spsv_jraw(&b, ",\"message\":");
    spsv_jstring(&b, issue->message);
    if (issue->location.present) {
      char location[192];
      (void)snprintf(location, sizeof(location),
                     ",\"location\":{\"byte_offset\":%zu,\"line\":%zu,"
                     "\"column\":%zu}",
                     issue->location.byte_offset, issue->location.line,
                     issue->location.column);
      spsv_jraw(&b, location);
    }
    spsv_jraw(&b, "}");
  }
  spsv_jraw(&b, "]}");
  if (b.failed) {
    free(b.data);
    return 0;
  }
  *out = b.data;
  *out_size = b.size;
  return 1;
}
