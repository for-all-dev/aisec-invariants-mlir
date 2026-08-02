#include "internal.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int spsv_result_invalid(sps_fixture_result *result, const char *code,
                               const char *path, const char *message,
                               const spsv_node *node) {
  (void)spsv_add_result_issue(
      result, SPS_FIXTURE_ISSUE_INVALID_INPUT,
      SPS_FIXTURE_PHASE_SNAPSHOT_VALIDATE, code, path, message,
      node ? &node->location : NULL);
  return 0;
}

static int spsv_result_closed(sps_fixture_result *result,
                              const spsv_node *map,
                              const char *const *keys, size_t key_count,
                              const char *path) {
  const char *bad = NULL;
  char *bad_path;
  if (spsv_map_has_only(map, keys, key_count, &bad)) return 1;
  bad_path = spsv_path_join(path, bad ? bad : "?");
  if (!bad_path) return 0;
  spsv_result_invalid(result, "UnknownField", bad_path,
                      "field is not permitted by the closed snapshot schema",
                      map);
  free(bad_path);
  return 0;
}

static const spsv_node *spsv_result_required(
    sps_fixture_result *result, const spsv_node *map, const char *key,
    spsv_node_kind kind, const char *path) {
  const spsv_node *node = spsv_map_get(map, key);
  if (!node) {
    spsv_result_invalid(result, "MissingField", path,
                        "required field is missing", map);
    return NULL;
  }
  if (node->kind != kind) {
    spsv_result_invalid(result, "WrongType", path,
                        "field has the wrong YAML type", node);
    return NULL;
  }
  return node;
}

static const char *spsv_position_name(sps_fixture_position_tag tag) {
  switch (tag) {
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

static int spsv_copy_actual(sps_fixture_result *result,
                            const sps_fixture_actual *actual) {
  const sps_fixture_position_view *source = &actual->view.position;
  result->case_id =
      spsv_strdup(actual->view.case_id.data ? actual->view.case_id.data : "");
  result->entry =
      spsv_strdup(actual->view.entry.data ? actual->view.entry.data : "");
  result->deployment =
      spsv_strdup(source->deployment.data ? source->deployment.data : "");
  result->policy = spsv_strdup(source->policy.data ? source->policy.data : "");
  if (!result->case_id || !result->entry || !result->deployment ||
      !result->policy)
    return 0;
  result->view.case_id = spsv_text_view(result->case_id);
  result->view.entry = spsv_text_view(result->entry);
  result->view.sensitivity = actual->view.sensitivity;
  result->view.position.tag = source->tag;
  result->view.position.deployment = spsv_text_view(result->deployment);
  result->view.position.policy = spsv_text_view(result->policy);
  if (source->tag == SPS_FIXTURE_POSITION_COUNTEREXAMPLE) {
    result->cause = spsv_strdup(source->detail.counterexample.cause.data);
    result->first_kind =
        spsv_strdup(source->detail.counterexample.first_difference.kind.data);
    result->first_field =
        spsv_strdup(source->detail.counterexample.first_difference.field.data);
    result->first_id =
        spsv_strdup(source->detail.counterexample.first_difference.id.data);
    if (!result->cause || !result->first_kind || !result->first_field ||
        !result->first_id)
      return 0;
    result->view.position.detail.counterexample.cause =
        spsv_text_view(result->cause);
    result->view.position.detail.counterexample.first_difference.kind =
        spsv_text_view(result->first_kind);
    result->view.position.detail.counterexample.first_difference.field =
        spsv_text_view(result->first_field);
    result->view.position.detail.counterexample.first_difference.id =
        spsv_text_view(result->first_id);
  } else if (source->tag == SPS_FIXTURE_POSITION_UNKNOWN) {
    result->reason = spsv_strdup(source->detail.unknown.reason.data);
    if (!result->reason) return 0;
    result->view.position.detail.unknown.reason =
        spsv_text_view(result->reason);
  }
  return 1;
}

static int spsv_mismatch(sps_fixture_result *result, const char *path,
                         const char *message) {
  result->view.comparison = SPS_FIXTURE_COMPARISON_MISMATCHED;
  return spsv_add_result_issue(
      result, SPS_FIXTURE_ISSUE_EXPECTATION_MISMATCH,
      SPS_FIXTURE_PHASE_COMPARE, "ExpectationMismatch", path, message, NULL);
}

static int spsv_consume_string(sps_fixture_result *result,
                               const char *expected_path,
                               const char *actual_path,
                               const spsv_node *expected,
                               const char *actual) {
  if (!expected || expected->kind != SPSV_NODE_STRING)
    return spsv_result_invalid(result, "WrongType", expected_path,
                               "expected value must be a string", expected);
  return spsv_add_consumption_strings(
      result, expected_path, actual_path, SPS_FIXTURE_CHECK_EXACT,
      actual && strcmp(expected->as.string, actual) == 0,
      expected->as.string, actual);
}

static int spsv_snapshot_event_valid(sps_fixture_result *result,
                                     const spsv_node *event,
                                     const char *path) {
  static const char *const keys[] = {"kind", "field", "id"};
  if (!event || event->kind != SPSV_NODE_MAPPING)
    return spsv_result_invalid(result, "WrongType", path,
                               "event selector must be a mapping", event);
  if (!spsv_result_closed(result, event, keys, 3, path)) return 0;
  if (!spsv_map_get(event, "kind") ||
      spsv_map_get(event, "kind")->kind != SPSV_NODE_STRING ||
      !spsv_map_get(event, "field") ||
      spsv_map_get(event, "field")->kind != SPSV_NODE_STRING ||
      (spsv_map_get(event, "id") &&
       spsv_map_get(event, "id")->kind != SPSV_NODE_STRING))
    return spsv_result_invalid(result, "InvalidEvent", path,
                               "event requires string kind and field", event);
  if (!spsv_event_pair_valid(spsv_map_get(event, "kind")->as.string,
                             spsv_map_get(event, "field")->as.string) ||
      (spsv_map_get(event, "id") &&
       !spsv_stable_id_valid(spsv_map_get(event, "id")->as.string)))
    return spsv_result_invalid(result, "InvalidEvent", path,
                               "event kind/field/id is outside the modeled domain",
                               event);
  return 1;
}

static int spsv_selector_equal(const spsv_node *left,
                               const spsv_node *right) {
  const spsv_node *lk = spsv_map_get(left, "kind");
  const spsv_node *lf = spsv_map_get(left, "field");
  const spsv_node *li = spsv_map_get(left, "id");
  const spsv_node *rk = spsv_map_get(right, "kind");
  const spsv_node *rf = spsv_map_get(right, "field");
  const spsv_node *ri = spsv_map_get(right, "id");
  return strcmp(lk->as.string, rk->as.string) == 0 &&
         strcmp(lf->as.string, rf->as.string) == 0 &&
         ((!li && !ri) ||
          (li && ri && strcmp(li->as.string, ri->as.string) == 0));
}

static int spsv_compare_events(sps_fixture_result *result,
                               const spsv_node *expected,
                               const spsv_node *actual) {
  size_t i, j;
  char expected_path[128], actual_path[128];
  for (i = 0; i < expected->as.sequence.count; ++i) {
    (void)snprintf(expected_path, sizeof(expected_path), "/expect/events/%zu",
                   i);
    if (!spsv_snapshot_event_valid(result, expected->as.sequence.items[i],
                                   expected_path))
      return 0;
    for (j = 0; j < i; ++j)
      if (spsv_selector_equal(expected->as.sequence.items[i],
                              expected->as.sequence.items[j]))
        return spsv_result_invalid(result, "DuplicateEvent",
                                   "/expect/events",
                                   "expected event selectors must be unique",
                                   expected->as.sequence.items[i]);
  }
  for (i = 0; i < expected->as.sequence.count; ++i) {
    const spsv_node *ee = expected->as.sequence.items[i];
    const spsv_node *ae = NULL;
    const spsv_node *expected_id = spsv_map_get(ee, "id");
    const spsv_node *actual_id;
    size_t actual_index = 0;
    for (j = 0; j < actual->as.sequence.count; ++j)
      if (spsv_selector_equal(ee, actual->as.sequence.items[j])) {
        ae = actual->as.sequence.items[j];
        actual_index = j;
        break;
      }
    actual_id = ae ? spsv_map_get(ae, "id") : NULL;
    (void)snprintf(expected_path, sizeof(expected_path),
                   "/expect/events/%zu/kind", i);
    (void)snprintf(actual_path, sizeof(actual_path),
                   "/decision/event_coverage/%zu/kind", actual_index);
    if (ae ? !spsv_consume_string(result, expected_path, actual_path,
                                  spsv_map_get(ee, "kind"),
                                  spsv_map_get(ae, "kind")->as.string)
           : !spsv_add_consumption(result, expected_path, "",
                                   SPS_FIXTURE_CHECK_EXACT, 0,
                                   spsv_map_get(ee, "kind"), NULL))
      return 0;
    (void)snprintf(expected_path, sizeof(expected_path),
                   "/expect/events/%zu/field", i);
    (void)snprintf(actual_path, sizeof(actual_path),
                   "/decision/event_coverage/%zu/field", actual_index);
    if (ae ? !spsv_consume_string(result, expected_path, actual_path,
                                  spsv_map_get(ee, "field"),
                                  spsv_map_get(ae, "field")->as.string)
           : !spsv_add_consumption(result, expected_path, "",
                                   SPS_FIXTURE_CHECK_EXACT, 0,
                                   spsv_map_get(ee, "field"), NULL))
      return 0;
    if (expected_id) {
      (void)snprintf(expected_path, sizeof(expected_path),
                     "/expect/events/%zu/id", i);
      (void)snprintf(actual_path, sizeof(actual_path),
                     "/decision/event_coverage/%zu/id", actual_index);
      if (actual_id ? !spsv_consume_string(result, expected_path, actual_path,
                                           expected_id, actual_id->as.string)
                    : !spsv_add_consumption(
                          result, expected_path, "",
                          SPS_FIXTURE_CHECK_EXACT, 0, expected_id, NULL))
        return 0;
    }
  }
  for (i = 0; i < actual->as.sequence.count; ++i) {
    int found = 0;
    for (j = 0; j < expected->as.sequence.count; ++j)
      if (spsv_selector_equal(actual->as.sequence.items[i],
                              expected->as.sequence.items[j]))
        found = 1;
    if (!found &&
        !spsv_mismatch(result, "/expect/events",
                       "actual event coverage contains an unexpected selector"))
      return 0;
  }
  return 1;
}

static int spsv_list_contains(const spsv_node *list,
                              const spsv_node *needle) {
  size_t i;
  if (!list || list->kind != SPSV_NODE_SEQUENCE) return 0;
  for (i = 0; i < list->as.sequence.count; ++i)
    if (spsv_node_equal(list->as.sequence.items[i], needle)) return 1;
  return 0;
}

static int spsv_match_contains(const spsv_node *expected,
                               const spsv_node *actual) {
  size_t i;
  if (!expected || expected->kind != SPSV_NODE_SEQUENCE ||
      !actual || actual->kind != SPSV_NODE_SEQUENCE)
    return 0;
  for (i = 0; i < expected->as.sequence.count; ++i)
    if (!spsv_list_contains(actual, expected->as.sequence.items[i])) return 0;
  return 1;
}

static int spsv_match_excludes(const spsv_node *expected,
                               const spsv_node *actual) {
  size_t i;
  if (!expected || expected->kind != SPSV_NODE_SEQUENCE ||
      !actual || actual->kind != SPSV_NODE_SEQUENCE)
    return 0;
  for (i = 0; i < expected->as.sequence.count; ++i)
    if (spsv_list_contains(actual, expected->as.sequence.items[i])) return 0;
  return 1;
}

static int spsv_match_ordered(const spsv_node *expected,
                              const spsv_node *actual) {
  size_t i, cursor = 0;
  if (!expected || expected->kind != SPSV_NODE_SEQUENCE ||
      !actual || actual->kind != SPSV_NODE_SEQUENCE)
    return 0;
  for (i = 0; i < actual->as.sequence.count &&
              cursor < expected->as.sequence.count;
       ++i)
    if (spsv_node_equal(actual->as.sequence.items[i],
                        expected->as.sequence.items[cursor]))
      ++cursor;
  return cursor == expected->as.sequence.count;
}

static int spsv_fact_count(const spsv_node *actual, int64_t *out) {
  if (!actual) return 0;
  if (actual->kind == SPSV_NODE_SEQUENCE) {
    if (actual->as.sequence.count > INT64_MAX) return 0;
    *out = (int64_t)actual->as.sequence.count;
    return 1;
  }
  if (actual->kind == SPSV_NODE_MAPPING) {
    if (actual->as.mapping.count > INT64_MAX) return 0;
    *out = (int64_t)actual->as.mapping.count;
    return 1;
  }
  return 0;
}

static int spsv_match_property(sps_fixture_result *result,
                               const char *pipeline_id,
                               const char *property_id,
                               const spsv_node *matcher,
                               const spsv_node *actual) {
  static const char *const matcher_keys[] = {
      "equals", "contains", "excludes", "ordered", "count"};
  static const char *const count_keys[] = {"eq", "min", "max"};
  char base[512], actual_path[512], path[560];
  const spsv_node *op;
  size_t operators = 0, i;
  (void)snprintf(base, sizeof(base), "/expect/pipelines/%s/properties/%s",
                 pipeline_id, property_id);
  (void)snprintf(actual_path, sizeof(actual_path), "/captures/%s/facts/%s",
                 pipeline_id, property_id);
  if (!matcher || matcher->kind != SPSV_NODE_MAPPING ||
      !spsv_result_closed(result, matcher, matcher_keys, 5, base))
    return spsv_result_invalid(result, "InvalidMatcher", base,
                               "property matcher must be a closed mapping",
                               matcher);
  for (i = 0; i < matcher->as.mapping.count; ++i) ++operators;
  if (operators == 0)
    return spsv_result_invalid(result, "InvalidMatcher", base,
                               "property matcher cannot be empty", matcher);
  op = spsv_map_get(matcher, "equals");
  if (op) {
    (void)snprintf(path, sizeof(path), "%s/equals", base);
    if (!spsv_add_consumption(result, path, actual_path,
                              SPS_FIXTURE_CHECK_EQUALS,
                              actual && spsv_node_equal(op, actual), op,
                              actual))
      return 0;
  }
  op = spsv_map_get(matcher, "contains");
  if (op) {
    if (op->kind != SPSV_NODE_SEQUENCE)
      return spsv_result_invalid(result, "WrongType", base,
                                 "contains must be a sequence", op);
    (void)snprintf(path, sizeof(path), "%s/contains", base);
    if (!spsv_add_consumption(result, path, actual_path,
                              SPS_FIXTURE_CHECK_CONTAINS,
                              spsv_match_contains(op, actual), op, actual))
      return 0;
  }
  op = spsv_map_get(matcher, "excludes");
  if (op) {
    if (op->kind != SPSV_NODE_SEQUENCE)
      return spsv_result_invalid(result, "WrongType", base,
                                 "excludes must be a sequence", op);
    (void)snprintf(path, sizeof(path), "%s/excludes", base);
    if (!spsv_add_consumption(result, path, actual_path,
                              SPS_FIXTURE_CHECK_EXCLUDES,
                              spsv_match_excludes(op, actual), op, actual))
      return 0;
  }
  op = spsv_map_get(matcher, "ordered");
  if (op) {
    if (op->kind != SPSV_NODE_SEQUENCE)
      return spsv_result_invalid(result, "WrongType", base,
                                 "ordered must be a sequence", op);
    (void)snprintf(path, sizeof(path), "%s/ordered", base);
    if (!spsv_add_consumption(result, path, actual_path,
                              SPS_FIXTURE_CHECK_ORDERED,
                              spsv_match_ordered(op, actual), op, actual))
      return 0;
  }
  op = spsv_map_get(matcher, "count");
  if (op) {
    int64_t actual_count = -1;
    int has_count;
    spsv_node actual_node;
    if (op->kind != SPSV_NODE_MAPPING ||
        !spsv_result_closed(result, op, count_keys, 3, base) ||
        op->as.mapping.count == 0)
      return spsv_result_invalid(result, "InvalidMatcher", base,
                                 "count must be a nonempty closed mapping", op);
    if ((spsv_map_get(op, "eq") &&
         (spsv_map_get(op, "min") || spsv_map_get(op, "max"))) ||
        (spsv_map_get(op, "min") && spsv_map_get(op, "max") &&
         (spsv_map_get(op, "min")->kind != SPSV_NODE_INTEGER ||
          spsv_map_get(op, "max")->kind != SPSV_NODE_INTEGER ||
          spsv_map_get(op, "min")->as.integer >
              spsv_map_get(op, "max")->as.integer)))
      return spsv_result_invalid(result, "InvalidMatcher", base,
                                 "count is either eq or consistent min/max bounds",
                                 op);
    memset(&actual_node, 0, sizeof(actual_node));
    actual_node.kind = SPSV_NODE_INTEGER;
    has_count = spsv_fact_count(actual, &actual_count);
    actual_node.as.integer = actual_count;
#define SPSV_COUNT_OP(name, check_kind, expression)                           \
    do {                                                                      \
      const spsv_node *bound = spsv_map_get(op, (name));                     \
      if (bound) {                                                            \
        if (bound->kind != SPSV_NODE_INTEGER || bound->as.integer < 0)       \
          return spsv_result_invalid(result, "WrongType", base,              \
                                     "count bound must be nonnegative",       \
                                     bound);                                  \
        (void)snprintf(path, sizeof(path), "%s/count/%s", base, (name));     \
        if (!spsv_add_consumption(result, path, actual_path, (check_kind),    \
                                  has_count && (expression), bound,           \
                                  has_count ? &actual_node : NULL))           \
          return 0;                                                          \
      }                                                                       \
    } while (0)
    SPSV_COUNT_OP("eq", SPS_FIXTURE_CHECK_COUNT_EQ,
                  actual_count == bound->as.integer);
    SPSV_COUNT_OP("min", SPS_FIXTURE_CHECK_COUNT_MIN,
                  actual_count >= bound->as.integer);
    SPSV_COUNT_OP("max", SPS_FIXTURE_CHECK_COUNT_MAX,
                  actual_count <= bound->as.integer);
#undef SPSV_COUNT_OP
  }
  return 1;
}

static int spsv_compare_pipeline(sps_fixture_result *result,
                                 const sps_fixture_actual *actual,
                                 const char *id,
                                 const spsv_node *expected) {
  static const char *const keys[] = {"kind", "properties", "sha256"};
  const spsv_node *kind, *properties, *digest, *capture, *state;
  const spsv_node *actual_kind, *facts;
  char expected_path[512], actual_path[512];
  size_t i;
  size_t issues_before = result->issue_count;
  if (!spsv_pipeline_id_valid(id))
    return spsv_result_invalid(result, "InvalidIdentifier",
                               "/expect/pipelines",
                               "pipeline key is not a pipeline identifier",
                               expected);
  if (!expected || expected->kind != SPSV_NODE_MAPPING) {
    (void)snprintf(expected_path, sizeof(expected_path),
                   "/expect/pipelines/%s", id);
    return spsv_result_invalid(result, "WrongType", expected_path,
                               "pipeline expectation must be a mapping",
                               expected);
  }
  (void)snprintf(expected_path, sizeof(expected_path), "/expect/pipelines/%s",
                 id);
  if (!spsv_result_closed(result, expected, keys, 3, expected_path)) return 0;
  kind = spsv_map_get(expected, "kind");
  properties = spsv_map_get(expected, "properties");
  digest = spsv_map_get(expected, "sha256");
  if (!kind || kind->kind != SPSV_NODE_STRING ||
      !spsv_pipeline_kind_valid(kind->as.string))
    return spsv_result_invalid(result, "InvalidPipeline", expected_path,
                               "pipeline kind is missing or invalid", kind);
  if (digest && properties)
    return spsv_result_invalid(result, "InvalidPipeline", expected_path,
                               "pipeline cannot have both properties and sha256",
                               expected);
  if (strcmp(kind->as.string, "bytes") == 0 &&
      (!digest || properties || !spsv_is_sha256(digest)))
    return spsv_result_invalid(result, "InvalidPipeline", expected_path,
                               "byte pipeline requires lowercase sha256",
                               expected);
  if (strcmp(kind->as.string, "bytes") != 0 &&
      (digest || !properties || properties->kind != SPSV_NODE_MAPPING ||
       properties->as.mapping.count == 0))
    return spsv_result_invalid(result, "WrongType", expected_path,
                               "structured pipeline requires nonempty properties",
                               properties);
  if (properties)
    for (i = 0; i < properties->as.mapping.count; ++i)
      if (!spsv_fact_key_valid(properties->as.mapping.items[i].key))
        return spsv_result_invalid(result, "InvalidIdentifier",
                                   expected_path,
                                   "property key is not a field path",
                                   properties->as.mapping.items[i].value);
  capture = spsv_map_get(actual->captures, id);
  if (!capture) {
    return spsv_result_invalid(result, "MissingCapture", expected_path,
                               "required pipeline capture is missing",
                               expected);
  }
  state = spsv_map_get(capture, "state");
  if (!state || strcmp(state->as.string, "Captured") != 0) {
    return spsv_result_invalid(result, "CaptureUnavailable", expected_path,
                               "required pipeline is not Captured", capture);
  }
  actual_kind = spsv_map_get(capture, "kind");
  if (strcmp(kind->as.string, actual_kind->as.string) != 0)
    return spsv_result_invalid(result, "CaptureKindMismatch", expected_path,
                               "required capture kind differs from the snapshot binding",
                               capture);
  (void)snprintf(expected_path, sizeof(expected_path),
                 "/expect/pipelines/%s/kind", id);
  (void)snprintf(actual_path, sizeof(actual_path), "/captures/%s/kind", id);
  if (!spsv_consume_string(result, expected_path, actual_path, kind,
                           actual_kind->as.string))
    return 0;
  if (digest) {
    const spsv_node *actual_digest =
        spsv_map_get(capture, "endpoint_sha256");
    (void)snprintf(expected_path, sizeof(expected_path),
                   "/expect/pipelines/%s/sha256", id);
    (void)snprintf(actual_path, sizeof(actual_path),
                   "/captures/%s/endpoint_sha256", id);
    if (!spsv_add_consumption(
            result, expected_path, actual_path, SPS_FIXTURE_CHECK_EXACT,
            spsv_node_equal(digest, actual_digest), digest, actual_digest))
      return 0;
  }
  facts = spsv_map_get(capture, "facts");
  if (properties)
    for (i = 0; i < properties->as.mapping.count; ++i) {
      const char *property_id = properties->as.mapping.items[i].key;
      if (!spsv_match_property(
              result, id, property_id, properties->as.mapping.items[i].value,
              spsv_map_get(facts, property_id)))
        return 0;
    }
  return spsv_add_pipeline(
      result, id,
      result->issue_count > issues_before
          ? SPS_FIXTURE_COMPARISON_MISMATCHED
          : SPS_FIXTURE_COMPARISON_MATCHED);
}

static int spsv_compare_position(sps_fixture_result *result,
                                 const spsv_node *position) {
  static const char *const proved_keys[] = {"tag"};
  static const char *const cex_keys[] = {
      "tag", "cause", "first_difference"};
  static const char *const unknown_keys[] = {"tag", "reason"};
  const spsv_node *tag, *first;
  const char *actual_tag = spsv_position_name(result->view.position.tag);
  tag = spsv_map_get(position, "tag");
  if (!tag || tag->kind != SPSV_NODE_STRING)
    return spsv_result_invalid(result, "MissingField",
                               "/expect/position/tag",
                               "position tag is required", position);
  if (strcmp(tag->as.string, "Proved") == 0) {
    if (!spsv_result_closed(result, position, proved_keys, 1,
                            "/expect/position"))
      return 0;
  } else if (strcmp(tag->as.string, "Counterexample") == 0) {
    const spsv_node *cause;
    const spsv_node *expected_id;
    if (!spsv_result_closed(result, position, cex_keys, 3,
                            "/expect/position"))
      return 0;
    cause = spsv_map_get(position, "cause");
    first = spsv_map_get(position, "first_difference");
    if (!cause || cause->kind != SPSV_NODE_STRING ||
        !spsv_stable_id_valid(cause->as.string) ||
        !spsv_snapshot_event_valid(
            result, first, "/expect/position/first_difference"))
      return spsv_result_invalid(result, "InvalidPosition",
                                 "/expect/position",
                                 "Counterexample requires cause and first difference",
                                 position);
    if (!spsv_consume_string(
            result, "/expect/position/cause",
            "/decision/counterexample/cause", cause,
            result->view.position.tag == SPS_FIXTURE_POSITION_COUNTEREXAMPLE
                ? result->cause
                : NULL))
      return 0;
    if (!spsv_consume_string(
            result, "/expect/position/first_difference/kind",
            "/decision/counterexample/first_difference/kind",
            spsv_map_get(first, "kind"),
            result->view.position.tag == SPS_FIXTURE_POSITION_COUNTEREXAMPLE
                ? result->first_kind
                : NULL))
      return 0;
    if (!spsv_consume_string(
            result, "/expect/position/first_difference/field",
            "/decision/counterexample/first_difference/field",
            spsv_map_get(first, "field"),
            result->view.position.tag == SPS_FIXTURE_POSITION_COUNTEREXAMPLE
                ? result->first_field
                : NULL))
      return 0;
    expected_id = spsv_map_get(first, "id");
    if (expected_id &&
        !spsv_consume_string(
            result, "/expect/position/first_difference/id",
            "/decision/counterexample/first_difference/id", expected_id,
            result->view.position.tag == SPS_FIXTURE_POSITION_COUNTEREXAMPLE
                ? result->first_id
                : NULL))
      return 0;
    if (!expected_id &&
        result->view.position.tag == SPS_FIXTURE_POSITION_COUNTEREXAMPLE &&
        result->first_id && result->first_id[0] &&
        !spsv_mismatch(result, "/expect/position/first_difference",
                       "actual first difference has an unexpected id"))
      return 0;
  } else if (strcmp(tag->as.string, "Unknown") == 0) {
    const spsv_node *reason;
    if (!spsv_result_closed(result, position, unknown_keys, 2,
                            "/expect/position"))
      return 0;
    reason = spsv_map_get(position, "reason");
    if (!reason || reason->kind != SPSV_NODE_STRING ||
        !spsv_stable_id_valid(reason->as.string))
      return spsv_result_invalid(result, "MissingField",
                                 "/expect/position/reason",
                                 "Unknown requires reason", position);
    if (!spsv_consume_string(
            result, "/expect/position/reason", "/decision/blockers", reason,
            result->view.position.tag == SPS_FIXTURE_POSITION_UNKNOWN
                ? result->reason
                : NULL))
      return 0;
  } else {
    return spsv_result_invalid(result, "InvalidEnum",
                               "/expect/position/tag",
                               "position tag must be Proved, Counterexample, or Unknown",
                               tag);
  }
  return spsv_consume_string(result, "/expect/position/tag",
                             "/derived/position/tag", tag, actual_tag);
}

int spsv_validate_and_compare_snapshot(sps_fixture_result *result,
                                       const sps_fixture_actual *actual) {
  static const char *const root_keys[] = {
      "format", "case", "entry", "expect", "because"};
  static const char *const expect_keys[] = {
      "position", "deployment", "policy", "events", "pipelines"};
  const spsv_node *root = result->snapshot_root;
  const spsv_node *format, *case_id, *entry, *expect, *because;
  const spsv_node *position, *deployment, *policy, *events, *pipelines;
  size_t i;
  if (!spsv_copy_actual(result, actual)) return 0;
  if (!root || root->kind != SPSV_NODE_MAPPING)
    return spsv_result_invalid(result, "WrongType", "",
                               "snapshot root must be a mapping", root);
  if (!spsv_result_closed(result, root, root_keys, 5, "")) return 0;
  format = spsv_result_required(result, root, "format", SPSV_NODE_STRING,
                                "/format");
  case_id =
      spsv_result_required(result, root, "case", SPSV_NODE_STRING, "/case");
  entry =
      spsv_result_required(result, root, "entry", SPSV_NODE_STRING, "/entry");
  expect = spsv_result_required(result, root, "expect", SPSV_NODE_MAPPING,
                                "/expect");
  because = spsv_result_required(result, root, "because", SPSV_NODE_STRING,
                                 "/because");
  if (!format || !case_id || !entry || !expect || !because) return 0;
  if (strcmp(format->as.string, "SPS-Harness-Fixture-Snapshot") != 0)
    return spsv_result_invalid(result, "WrongFormat", "/format",
                               "unexpected snapshot format", format);
  if (!spsv_case_id_valid(case_id->as.string) ||
      !spsv_mlir_symbol_valid(entry->as.string))
    return spsv_result_invalid(result, "InvalidIdentifier", "/case",
                               "case or entry does not match its identifier grammar",
                               case_id);
  if (because->as.string[0] == '\0' ||
      spsv_utf8_length(because->as.string) > 8192)
    return spsv_result_invalid(result, "InvalidExplanation", "/because",
                               "because must contain 1 to 8192 UTF-8 code points",
                               because);
  if (!spsv_result_closed(result, expect, expect_keys, 5, "/expect")) return 0;
  position = spsv_result_required(result, expect, "position",
                                  SPSV_NODE_MAPPING, "/expect/position");
  deployment = spsv_result_required(result, expect, "deployment",
                                    SPSV_NODE_STRING, "/expect/deployment");
  policy = spsv_result_required(result, expect, "policy", SPSV_NODE_STRING,
                                "/expect/policy");
  events = spsv_result_required(result, expect, "events", SPSV_NODE_SEQUENCE,
                                "/expect/events");
  pipelines = spsv_result_required(result, expect, "pipelines",
                                   SPSV_NODE_MAPPING, "/expect/pipelines");
  if (!position || !deployment || !policy || !events || !pipelines) return 0;
  if (strcmp(deployment->as.string, "Open") != 0 ||
      !spsv_policy_valid(policy->as.string))
    return spsv_result_invalid(result, "InvalidFinalAxis", "/expect",
                               "deployment must be Open and policy must be modeled",
                               expect);
  if (pipelines->as.mapping.count == 0)
    return spsv_result_invalid(result, "MissingPipeline",
                               "/expect/pipelines",
                               "snapshot requires at least one pipeline",
                               pipelines);
  if (spsv_map_get(position, "tag") &&
      spsv_map_get(position, "tag")->kind == SPSV_NODE_STRING &&
      strcmp(spsv_map_get(position, "tag")->as.string, "Proved") == 0 &&
      events->as.sequence.count == 0)
    return spsv_result_invalid(result, "MissingEventCoverage",
                               "/expect/events",
                               "Proved expectation requires event coverage",
                               events);
  if (!spsv_consume_string(result, "/case", "/case", case_id,
                           result->case_id) ||
      !spsv_consume_string(result, "/entry", "/entry", entry, result->entry) ||
      !spsv_compare_position(result, position) ||
      !spsv_consume_string(result, "/expect/deployment",
                           "/decision/deployment", deployment,
                           result->deployment) ||
      !spsv_consume_string(result, "/expect/policy", "/decision/policy",
                           policy, result->policy) ||
      !spsv_compare_events(result, events, actual->event_coverage))
    return 0;
  if (strcmp(spsv_map_get(position, "tag")->as.string,
             "Counterexample") == 0) {
    const spsv_node *first = spsv_map_get(position, "first_difference");
    int found = 0;
    for (i = 0; i < events->as.sequence.count; ++i)
      if (spsv_selector_equal(first, events->as.sequence.items[i])) found = 1;
    if (!found)
      return spsv_result_invalid(
          result, "UncoveredFirstDifference",
          "/expect/position/first_difference",
          "expected first difference must occur in expected event coverage",
          first);
  }
  for (i = 0; i < pipelines->as.mapping.count; ++i)
    if (!spsv_compare_pipeline(result, actual,
                               pipelines->as.mapping.items[i].key,
                               pipelines->as.mapping.items[i].value))
      return 0;
  if (!spsv_add_ignored(result, "/because")) return 0;
  return 1;
}
