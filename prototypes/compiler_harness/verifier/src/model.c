#include "internal.h"

#include <stdlib.h>
#include <string.h>

static int spsv_ascii_alnum(char c) {
  return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
         (c >= '0' && c <= '9');
}

size_t spsv_utf8_length(const char *value) {
  size_t i, count = 0;
  for (i = 0; value && value[i]; ++i)
    if (((unsigned char)value[i] & 0xc0u) != 0x80u) ++count;
  return count;
}

int spsv_case_id_valid(const char *value) {
  size_t i, n;
  int slash = 0, segment_start = 1;
  if (!value || (n = strlen(value)) == 0 || n > 512) return 0;
  for (i = 0; i < n; ++i) {
    char c = value[i];
    if (c == '/') {
      if (segment_start) return 0;
      slash = 1;
      segment_start = 1;
    } else {
      if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
            (!segment_start && c == '-')))
        return 0;
      segment_start = 0;
    }
  }
  return slash && !segment_start;
}

int spsv_mlir_symbol_valid(const char *value) {
  size_t i, n;
  if (!value || (n = strlen(value)) == 0 || n > 256) return 0;
  if (!((value[0] >= 'A' && value[0] <= 'Z') ||
        (value[0] >= 'a' && value[0] <= 'z') || value[0] == '_' ||
        value[0] == '.' || value[0] == '$'))
    return 0;
  for (i = 1; i < n; ++i)
    if (!(spsv_ascii_alnum(value[i]) || value[i] == '_' || value[i] == '.' ||
          value[i] == '$' || value[i] == '-'))
      return 0;
  return 1;
}

int spsv_stable_id_valid(const char *value) {
  size_t i, n;
  if (!value || (n = strlen(value)) == 0 || n > 256) return 0;
  if (!((value[0] >= 'A' && value[0] <= 'Z') ||
        (value[0] >= 'a' && value[0] <= 'z')))
    return 0;
  for (i = 1; i < n; ++i)
    if (!(spsv_ascii_alnum(value[i]) || value[i] == '.' || value[i] == '_' ||
          value[i] == '-'))
      return 0;
  return 1;
}

int spsv_pipeline_id_valid(const char *value) {
  size_t i, n;
  int after_hyphen = 0;
  if (!value || (n = strlen(value)) == 0 || n > 128 ||
      value[0] < 'a' || value[0] > 'z')
    return 0;
  for (i = 1; i < n; ++i) {
    char c = value[i];
    if (c == '-') {
      if (after_hyphen || i + 1 == n) return 0;
      after_hyphen = 1;
    } else if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
      after_hyphen = 0;
    } else {
      return 0;
    }
  }
  return 1;
}

int spsv_fact_key_valid(const char *value) {
  size_t i, n;
  if (!value || (n = strlen(value)) == 0 || n > 256 ||
      !spsv_ascii_alnum(value[0]))
    return 0;
  for (i = 1; value[i]; ++i)
    if (!(spsv_ascii_alnum(value[i]) || value[i] == '.' || value[i] == '_' ||
          value[i] == '-'))
      return 0;
  return 1;
}

int spsv_pipeline_kind_valid(const char *value) {
  static const char *const values[] = {
      "mlir", "llvm-ir", "mir", "assembly", "object",
      "bytes", "diagnostic", "json", "relation-reference"};
  size_t i;
  for (i = 0; i < sizeof(values) / sizeof(values[0]); ++i)
    if (strcmp(value, values[i]) == 0) return 1;
  return 0;
}

int spsv_policy_valid(const char *value) {
  return value && (strcmp(value, "Complete") == 0 ||
                   strcmp(value, "Findings") == 0 ||
                   strcmp(value, "Incomplete") == 0);
}

int spsv_event_pair_valid(const char *kind, const char *field) {
  static const struct {
    const char *kind;
    const char *fields[6];
  } table[] = {
      {"BranchSuccessor", {"successor", NULL}},
      {"SwitchSuccessor", {"successor", NULL}},
      {"CalleeChoice", {"callee", NULL}},
      {"LoopContinuation", {"continueOrExit", NULL}},
      {"Failure", {"class", NULL}},
      {"Termination", {"returnClass", NULL}},
      {"BoundExhausted", {"boundId", NULL}},
      {"UBRisk", {"reasonClass", NULL}},
      {"Memory", {"allocationClass", "offsetClass", "width", "addressSpace",
                  "readOrWrite", NULL}},
      {"Transfer", {"source", "destinations", "width", "representation",
                    "valueBytes", "metadata"}},
      {"Output", {"outputId", "footprint", "valueBytes", NULL}},
      {"Release", {"releaseId", "releaseOrdinal", "valueBytes", "footprint",
                   NULL}},
      {"Error", {"errorFieldId", "class", "payload", NULL}},
      {"Latency", {"configuredClass", NULL}},
      {"ContractMeta", {"contractId", "metadataFieldId", "typedValue", NULL}}};
  size_t i, j;
  for (i = 0; i < sizeof(table) / sizeof(table[0]); ++i)
    if (strcmp(kind, table[i].kind) == 0)
      for (j = 0; j < sizeof(table[i].fields) / sizeof(table[i].fields[0]);
           ++j) {
        if (!table[i].fields[j]) return 0;
        if (strcmp(field, table[i].fields[j]) == 0) return 1;
      }
  return 0;
}

static int spsv_forbidden_fact_key(const char *key) {
  static const char *const forbidden_prefixes[] = {
      "because",     "comparison", "expect",         "match",
      "mismatch",    "modelstatus", "outcome",        "position",
      "snapshot",    "spsmodelstatus", "testoutcome"};
  char normalized[256];
  size_t i, n = 0;
  for (i = 0; key[i] && n + 1 < sizeof(normalized); ++i)
    if (spsv_ascii_alnum(key[i])) {
      char c = key[i];
      normalized[n++] = (c >= 'A' && c <= 'Z') ? (char)(c + 32) : c;
    }
  normalized[n] = '\0';
  for (i = 0;
       i < sizeof(forbidden_prefixes) / sizeof(forbidden_prefixes[0]); ++i)
    if (strncmp(normalized, forbidden_prefixes[i],
                strlen(forbidden_prefixes[i])) == 0)
      return 1;
  return 0;
}

static int spsv_facts_check(const spsv_node *node, int top_level) {
  size_t i;
  if (!node) return 0;
  if (node->kind == SPSV_NODE_MAPPING) {
    for (i = 0; i < node->as.mapping.count; ++i) {
      if ((top_level && !spsv_fact_key_valid(node->as.mapping.items[i].key)) ||
          spsv_forbidden_fact_key(node->as.mapping.items[i].key) ||
          !spsv_facts_check(node->as.mapping.items[i].value, 0))
        return 0;
    }
  } else if (node->kind == SPSV_NODE_SEQUENCE) {
    for (i = 0; i < node->as.sequence.count; ++i)
      if (!spsv_facts_check(node->as.sequence.items[i], 0)) return 0;
  }
  return 1;
}

int spsv_facts_expectation_blind(const spsv_node *node) {
  return spsv_facts_check(node, 1);
}

sps_fixture_text_view spsv_text_view(const char *text) {
  sps_fixture_text_view view;
  view.data = text ? text : "";
  view.size = text ? strlen(text) : 0;
  return view;
}

sps_fixture_issue_view spsv_issue_view(const spsv_issue *issue) {
  sps_fixture_issue_view view;
  view.kind = issue->kind;
  view.phase = issue->phase;
  view.code = spsv_text_view(issue->code);
  view.path = spsv_text_view(issue->path);
  view.message = spsv_text_view(issue->message);
  view.location = issue->location;
  return view;
}

static void spsv_issue_destroy(spsv_issue *issue) {
  free(issue->code);
  free(issue->path);
  free(issue->message);
}

static int spsv_add_issue(spsv_issue **items, size_t *count, size_t *capacity,
                          sps_fixture_issue_kind kind,
                          sps_fixture_issue_phase phase, const char *code,
                          const char *path, const char *message,
                          const sps_fixture_source_location *location) {
  spsv_issue *grown;
  spsv_issue issue;
  size_t next;
  if (*count == *capacity) {
    next = *capacity ? *capacity * 2 : 4;
    if (next > SIZE_MAX / sizeof(*grown)) return 0;
    grown = (spsv_issue *)realloc(*items, next * sizeof(*grown));
    if (!grown) return 0;
    *items = grown;
    *capacity = next;
  }
  memset(&issue, 0, sizeof(issue));
  issue.kind = kind;
  issue.phase = phase;
  issue.code = spsv_strdup(code);
  issue.path = spsv_strdup(path);
  issue.message = spsv_strdup(message);
  if (!issue.code || !issue.path || !issue.message) {
    spsv_issue_destroy(&issue);
    return 0;
  }
  if (location) issue.location = *location;
  (*items)[(*count)++] = issue;
  return 1;
}

int spsv_add_actual_issue(sps_fixture_actual *actual,
                          sps_fixture_issue_kind kind,
                          sps_fixture_issue_phase phase, const char *code,
                          const char *path, const char *message,
                          const sps_fixture_source_location *location) {
  int ok = spsv_add_issue(&actual->issues, &actual->issue_count,
                          &actual->issue_capacity, kind, phase, code, path,
                          message, location);
  if (!ok) actual->out_of_memory = 1;
  return ok;
}

int spsv_add_result_issue(sps_fixture_result *result,
                          sps_fixture_issue_kind kind,
                          sps_fixture_issue_phase phase, const char *code,
                          const char *path, const char *message,
                          const sps_fixture_source_location *location) {
  int ok = spsv_add_issue(&result->issues, &result->issue_count,
                          &result->issue_capacity, kind, phase, code, path,
                          message, location);
  if (!ok) result->out_of_memory = 1;
  return ok;
}

static char *spsv_json_string(const char *text) {
  size_t i, n = 2;
  char *out, *p;
  for (i = 0; text[i]; ++i) {
    unsigned char c = (unsigned char)text[i];
    if (c == '"' || c == '\\') n += 2;
    else if (c < 0x20) n += 6;
    else ++n;
  }
  if (n == SIZE_MAX) return NULL;
  out = (char *)malloc(n + 1);
  if (!out) return NULL;
  p = out;
  *p++ = '"';
  for (i = 0; text[i]; ++i) {
    unsigned char c = (unsigned char)text[i];
    static const char hex[] = "0123456789abcdef";
    if (c == '"' || c == '\\') {
      *p++ = '\\';
      *p++ = (char)c;
    } else if (c < 0x20) {
      *p++ = '\\';
      *p++ = 'u';
      *p++ = '0';
      *p++ = '0';
      *p++ = hex[c >> 4];
      *p++ = hex[c & 15u];
    } else {
      *p++ = (char)c;
    }
  }
  *p++ = '"';
  *p = '\0';
  return out;
}

static char *spsv_present_json(char *value) {
  static const char prefix[] = "{\"state\":\"Present\",\"value\":";
  size_t a = sizeof(prefix) - 1, b;
  char *out;
  if (!value) return NULL;
  b = strlen(value);
  if (a > SIZE_MAX - b - 2) {
    free(value);
    return NULL;
  }
  out = (char *)malloc(a + b + 2);
  if (!out) {
    free(value);
    return NULL;
  }
  memcpy(out, prefix, a);
  memcpy(out + a, value, b);
  out[a + b] = '}';
  out[a + b + 1] = '\0';
  free(value);
  return out;
}

static int spsv_consumption_reserve(sps_fixture_result *result) {
  spsv_consumption *grown;
  size_t next;
  if (result->consumption_count < result->consumption_capacity) return 1;
  next = result->consumption_capacity ? result->consumption_capacity * 2 : 16;
  if (next > SIZE_MAX / sizeof(*grown)) return 0;
  grown = (spsv_consumption *)realloc(result->consumptions,
                                     next * sizeof(*grown));
  if (!grown) return 0;
  result->consumptions = grown;
  result->consumption_capacity = next;
  return 1;
}

static int spsv_add_consumption_owned(
    sps_fixture_result *result, const char *expected_path,
    const char *actual_path, sps_fixture_check_kind check,
    sps_fixture_consumption_disposition disposition, char *expected_json,
    char *actual_json) {
  spsv_consumption *row;
  spsv_consumption pending;
  if (!spsv_consumption_reserve(result)) {
    result->out_of_memory = 1;
    free(expected_json);
    free(actual_json);
    return 0;
  }
  memset(&pending, 0, sizeof(pending));
  pending.expectation_path = spsv_strdup(expected_path);
  pending.actual_path =
      actual_path ? spsv_strdup(actual_path) : spsv_strdup("");
  pending.check = check;
  pending.disposition = disposition;
  pending.expected_json = expected_json;
  pending.actual_json = actual_json;
  if (!pending.expectation_path || !pending.actual_path ||
      !pending.expected_json || !pending.actual_json) {
    free(pending.expectation_path);
    free(pending.actual_path);
    free(pending.expected_json);
    free(pending.actual_json);
    result->out_of_memory = 1;
    return 0;
  }
  row = &result->consumptions[result->consumption_count++];
  *row = pending;
  if (disposition == SPS_FIXTURE_CONSUMED_MISMATCHED) {
    result->view.comparison = SPS_FIXTURE_COMPARISON_MISMATCHED;
    if (!spsv_add_result_issue(
            result, SPS_FIXTURE_ISSUE_EXPECTATION_MISMATCH,
            SPS_FIXTURE_PHASE_COMPARE, "ExpectationMismatch", expected_path,
            "expected value did not match the independently derived trace",
            NULL))
      return 0;
  }
  return 1;
}

int spsv_add_consumption(sps_fixture_result *result, const char *expected_path,
                         const char *actual_path, sps_fixture_check_kind check,
                         int matched, const spsv_node *expected,
                         const spsv_node *actual) {
  return spsv_add_consumption_owned(
      result, expected_path, actual_path, check,
      matched ? SPS_FIXTURE_CONSUMED_MATCHED
              : SPS_FIXTURE_CONSUMED_MISMATCHED,
      spsv_node_json(expected),
      actual ? spsv_present_json(spsv_node_json(actual))
             : spsv_strdup("{\"state\":\"Missing\"}"));
}

int spsv_add_consumption_strings(
    sps_fixture_result *result, const char *expected_path,
    const char *actual_path, sps_fixture_check_kind check, int matched,
    const char *expected, const char *actual) {
  return spsv_add_consumption_owned(
      result, expected_path, actual_path, check,
      matched ? SPS_FIXTURE_CONSUMED_MATCHED
              : SPS_FIXTURE_CONSUMED_MISMATCHED,
      spsv_json_string(expected ? expected : ""),
      actual ? spsv_present_json(spsv_json_string(actual))
             : spsv_strdup("{\"state\":\"Missing\"}"));
}

int spsv_add_ignored(sps_fixture_result *result, const char *path) {
  return spsv_add_consumption_owned(
      result, path, "", SPS_FIXTURE_CHECK_IGNORED_EXPLANATION,
      SPS_FIXTURE_CONSUMED_IGNORED, spsv_strdup(""), spsv_strdup(""));
}

int spsv_add_pipeline(sps_fixture_result *result, const char *id,
                      sps_fixture_comparison comparison) {
  spsv_pipeline *grown;
  size_t next;
  if (result->pipeline_count == result->pipeline_capacity) {
    next = result->pipeline_capacity ? result->pipeline_capacity * 2 : 8;
    if (next > SIZE_MAX / sizeof(*grown)) {
      result->out_of_memory = 1;
      return 0;
    }
    grown =
        (spsv_pipeline *)realloc(result->pipelines, next * sizeof(*grown));
    if (!grown) {
      result->out_of_memory = 1;
      return 0;
    }
    result->pipelines = grown;
    result->pipeline_capacity = next;
  }
  result->pipelines[result->pipeline_count].pipeline = spsv_strdup(id);
  result->pipelines[result->pipeline_count].comparison = comparison;
  if (!result->pipelines[result->pipeline_count].pipeline) {
    result->out_of_memory = 1;
    return 0;
  }
  ++result->pipeline_count;
  return 1;
}

void sps_fixture_actual_destroy(sps_fixture_actual *actual) {
  size_t i;
  if (!actual) return;
  spsv_node_destroy(actual->root);
  free(actual->derived_reason);
  for (i = 0; i < actual->issue_count; ++i)
    spsv_issue_destroy(&actual->issues[i]);
  free(actual->issues);
  free(actual);
}

void sps_fixture_result_destroy(sps_fixture_result *result) {
  size_t i;
  if (!result) return;
  spsv_node_destroy(result->snapshot_root);
  free(result->case_id);
  free(result->entry);
  free(result->deployment);
  free(result->policy);
  free(result->cause);
  free(result->reason);
  free(result->first_kind);
  free(result->first_field);
  free(result->first_id);
  for (i = 0; i < result->pipeline_count; ++i)
    free(result->pipelines[i].pipeline);
  free(result->pipelines);
  for (i = 0; i < result->consumption_count; ++i) {
    free(result->consumptions[i].expectation_path);
    free(result->consumptions[i].actual_path);
    free(result->consumptions[i].expected_json);
    free(result->consumptions[i].actual_json);
  }
  free(result->consumptions);
  for (i = 0; i < result->issue_count; ++i)
    spsv_issue_destroy(&result->issues[i]);
  free(result->issues);
  free(result);
}

sps_fixture_status sps_fixture_actual_get_view(
    const sps_fixture_actual *actual, sps_fixture_actual_view *out_view) {
  if (!actual || !out_view) return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  *out_view = actual->view;
  return SPS_FIXTURE_STATUS_OK;
}

size_t sps_fixture_actual_issue_count(const sps_fixture_actual *actual) {
  return actual ? actual->issue_count : 0;
}

sps_fixture_status sps_fixture_actual_issue_at(
    const sps_fixture_actual *actual, size_t index,
    sps_fixture_issue_view *out_issue) {
  if (!actual || !out_issue) return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  if (index >= actual->issue_count) return SPS_FIXTURE_STATUS_OUT_OF_RANGE;
  *out_issue = spsv_issue_view(&actual->issues[index]);
  return SPS_FIXTURE_STATUS_OK;
}

size_t sps_fixture_actual_event_count(const sps_fixture_actual *actual) {
  if (!actual || !actual->event_coverage ||
      actual->event_coverage->kind != SPSV_NODE_SEQUENCE)
    return 0;
  return actual->event_coverage->as.sequence.count;
}

sps_fixture_status sps_fixture_actual_event_at(
    const sps_fixture_actual *actual, size_t index,
    sps_fixture_event_view *out_event) {
  const spsv_node *event, *kind, *field, *id;
  if (!actual || !out_event) return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  if (index >= sps_fixture_actual_event_count(actual))
    return SPS_FIXTURE_STATUS_OUT_OF_RANGE;
  event = actual->event_coverage->as.sequence.items[index];
  kind = spsv_map_get(event, "kind");
  field = spsv_map_get(event, "field");
  id = spsv_map_get(event, "id");
  out_event->kind = spsv_text_view(kind ? kind->as.string : "");
  out_event->field = spsv_text_view(field ? field->as.string : "");
  out_event->id = spsv_text_view(id ? id->as.string : "");
  return SPS_FIXTURE_STATUS_OK;
}

sps_fixture_status sps_fixture_result_get_view(
    const sps_fixture_result *result, sps_fixture_result_view *out_view) {
  if (!result || !out_view) return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  *out_view = result->view;
  return SPS_FIXTURE_STATUS_OK;
}

size_t sps_fixture_result_issue_count(const sps_fixture_result *result) {
  return result ? result->issue_count : 0;
}

sps_fixture_status sps_fixture_result_issue_at(
    const sps_fixture_result *result, size_t index,
    sps_fixture_issue_view *out_issue) {
  if (!result || !out_issue) return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  if (index >= result->issue_count) return SPS_FIXTURE_STATUS_OUT_OF_RANGE;
  *out_issue = spsv_issue_view(&result->issues[index]);
  return SPS_FIXTURE_STATUS_OK;
}

size_t sps_fixture_result_pipeline_count(const sps_fixture_result *result) {
  return result ? result->pipeline_count : 0;
}

sps_fixture_status sps_fixture_result_pipeline_at(
    const sps_fixture_result *result, size_t index,
    sps_fixture_pipeline_view *out_pipeline) {
  if (!result || !out_pipeline) return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  if (index >= result->pipeline_count) return SPS_FIXTURE_STATUS_OUT_OF_RANGE;
  out_pipeline->pipeline =
      spsv_text_view(result->pipelines[index].pipeline);
  out_pipeline->comparison = result->pipelines[index].comparison;
  return SPS_FIXTURE_STATUS_OK;
}

size_t sps_fixture_result_consumption_count(
    const sps_fixture_result *result) {
  return result ? result->consumption_count : 0;
}

sps_fixture_status sps_fixture_result_consumption_at(
    const sps_fixture_result *result, size_t index,
    sps_fixture_consumption_view *out_consumption) {
  const spsv_consumption *row;
  if (!result || !out_consumption) return SPS_FIXTURE_STATUS_INVALID_ARGUMENT;
  if (index >= result->consumption_count)
    return SPS_FIXTURE_STATUS_OUT_OF_RANGE;
  row = &result->consumptions[index];
  out_consumption->expectation_path =
      spsv_text_view(row->expectation_path);
  out_consumption->actual_path = spsv_text_view(row->actual_path);
  out_consumption->check = row->check;
  out_consumption->disposition = row->disposition;
  out_consumption->expected_json = spsv_text_view(row->expected_json);
  out_consumption->actual_json = spsv_text_view(row->actual_json);
  return SPS_FIXTURE_STATUS_OK;
}
