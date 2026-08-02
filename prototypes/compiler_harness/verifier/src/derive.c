#include "internal.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int spsv_invalid(sps_fixture_actual *actual, const char *code,
                        const char *path, const char *message,
                        const spsv_node *node,
                        sps_fixture_issue_phase phase) {
  return spsv_add_actual_issue(
             actual, SPS_FIXTURE_ISSUE_INVALID_INPUT, phase, code, path,
             message, node ? &node->location : NULL)
             ? 0
             : 0;
}

static const spsv_node *spsv_required(sps_fixture_actual *actual,
                                      const spsv_node *map, const char *key,
                                      spsv_node_kind kind, const char *path) {
  const spsv_node *node = spsv_map_get(map, key);
  if (!node) {
    spsv_invalid(actual, "MissingField", path, "required field is missing",
                 map, SPS_FIXTURE_PHASE_TRACE_VALIDATE);
    return NULL;
  }
  if (node->kind != kind) {
    spsv_invalid(actual, "WrongType", path, "field has the wrong YAML type",
                 node, SPS_FIXTURE_PHASE_TRACE_VALIDATE);
    return NULL;
  }
  return node;
}

static int spsv_closed(sps_fixture_actual *actual, const spsv_node *map,
                       const char *const *keys, size_t key_count,
                       const char *path) {
  const char *bad = NULL;
  char *bad_path;
  if (spsv_map_has_only(map, keys, key_count, &bad)) return 1;
  bad_path = spsv_path_join(path, bad ? bad : "?");
  if (!bad_path) return 0;
  spsv_invalid(actual, "UnknownField", bad_path,
               "field is not permitted by the closed trace schema", map,
               SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  free(bad_path);
  return 0;
}

static int spsv_string_is(const spsv_node *node, const char *value) {
  return node && node->kind == SPSV_NODE_STRING &&
         strcmp(node->as.string, value) == 0;
}

static int spsv_event_valid(sps_fixture_actual *actual, const spsv_node *event,
                            const char *path) {
  static const char *const keys[] = {"kind", "field", "id"};
  char *child;
  if (!event || event->kind != SPSV_NODE_MAPPING)
    return spsv_invalid(actual, "WrongType", path,
                        "event selector must be a mapping", event,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  if (!spsv_closed(actual, event, keys, 3, path)) return 0;
  child = spsv_path_join(path, "kind");
  if (!child) return 0;
  if (!spsv_required(actual, event, "kind", SPSV_NODE_STRING, child)) {
    free(child);
    return 0;
  }
  free(child);
  child = spsv_path_join(path, "field");
  if (!child) return 0;
  if (!spsv_required(actual, event, "field", SPSV_NODE_STRING, child)) {
    free(child);
    return 0;
  }
  free(child);
  if (!spsv_event_pair_valid(spsv_map_get(event, "kind")->as.string,
                             spsv_map_get(event, "field")->as.string))
    return spsv_invalid(actual, "InvalidEvent", path,
                        "event kind and field are not a modeled pair", event,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  if (spsv_map_get(event, "id") &&
      (spsv_map_get(event, "id")->kind != SPSV_NODE_STRING ||
       !spsv_stable_id_valid(spsv_map_get(event, "id")->as.string)))
    return spsv_invalid(actual, "WrongType", path,
                        "event id must be a stable identifier",
                        spsv_map_get(event, "id"),
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  return 1;
}

static int spsv_event_equal(const spsv_node *left, const spsv_node *right) {
  const spsv_node *lk = spsv_map_get(left, "kind");
  const spsv_node *lf = spsv_map_get(left, "field");
  const spsv_node *li = spsv_map_get(left, "id");
  const spsv_node *rk = spsv_map_get(right, "kind");
  const spsv_node *rf = spsv_map_get(right, "field");
  const spsv_node *ri = spsv_map_get(right, "id");
  return lk && rk && lf && rf &&
         strcmp(lk->as.string, rk->as.string) == 0 &&
         strcmp(lf->as.string, rf->as.string) == 0 &&
         ((!li && !ri) ||
          (li && ri && strcmp(li->as.string, ri->as.string) == 0));
}

static int spsv_validate_capture(sps_fixture_actual *actual, const char *id,
                                 const spsv_node *capture) {
  static const char *const captured_keys[] = {
      "state", "kind", "extractor", "endpoint_sha256", "facts"};
  static const char *const failed_keys[] = {
      "state", "kind", "extractor", "error", "blocked_by"};
  const spsv_node *state, *kind, *extractor, *blocked;
  char *path = spsv_path_join("/captures", id);
  size_t i;
  if (!path) return 0;
  if (!spsv_pipeline_id_valid(id)) {
    spsv_invalid(actual, "InvalidIdentifier", path,
                 "capture key is not a pipeline identifier", capture,
                 SPS_FIXTURE_PHASE_TRACE_VALIDATE);
    free(path);
    return 0;
  }
  if (!capture || capture->kind != SPSV_NODE_MAPPING) {
    spsv_invalid(actual, "WrongType", path, "capture must be a mapping",
                 capture, SPS_FIXTURE_PHASE_TRACE_VALIDATE);
    free(path);
    return 0;
  }
  state = spsv_map_get(capture, "state");
  kind = spsv_map_get(capture, "kind");
  extractor = spsv_map_get(capture, "extractor");
  if (!state || state->kind != SPSV_NODE_STRING || !kind ||
      kind->kind != SPSV_NODE_STRING || !extractor ||
      extractor->kind != SPSV_NODE_STRING ||
      !spsv_pipeline_kind_valid(kind->as.string) ||
      !spsv_stable_id_valid(extractor->as.string)) {
    spsv_invalid(actual, "MissingField", path,
                 "capture requires string state, kind, and extractor", capture,
                 SPS_FIXTURE_PHASE_TRACE_VALIDATE);
    free(path);
    return 0;
  }
  if (strcmp(state->as.string, "Captured") == 0) {
    const spsv_node *digest = spsv_map_get(capture, "endpoint_sha256");
    const spsv_node *facts = spsv_map_get(capture, "facts");
    if (!spsv_closed(actual, capture, captured_keys, 5, path) ||
        !spsv_is_sha256(digest) || !facts ||
        facts->kind != SPSV_NODE_MAPPING ||
        !spsv_facts_expectation_blind(facts)) {
      spsv_invalid(actual, "InvalidCapture", path,
                   "Captured requires a lowercase SHA-256 and facts mapping",
                   capture, SPS_FIXTURE_PHASE_TRACE_VALIDATE);
      free(path);
      return 0;
    }
  } else {
    const char *allowed[] = {"ProducerFailed", "ExtractionFailed",
                             "Unsupported", "Blocked"};
    int found = 0;
    for (i = 0; i < 4; ++i)
      if (strcmp(state->as.string, allowed[i]) == 0) found = 1;
    if (!found || !spsv_closed(actual, capture, failed_keys, 5, path) ||
        !spsv_map_get(capture, "error") ||
        spsv_map_get(capture, "error")->kind != SPSV_NODE_STRING ||
        spsv_map_get(capture, "error")->as.string[0] == '\0' ||
        spsv_utf8_length(spsv_map_get(capture, "error")->as.string) > 8192) {
      spsv_invalid(actual, "InvalidCapture", path,
                   "failure capture has an invalid state or missing error",
                   capture, SPS_FIXTURE_PHASE_TRACE_VALIDATE);
      free(path);
      return 0;
    }
    blocked = spsv_map_get(capture, "blocked_by");
    if (blocked) {
      if (blocked->kind != SPSV_NODE_SEQUENCE ||
          blocked->as.sequence.count == 0) {
        spsv_invalid(actual, "WrongType", path,
                     "blocked_by must be a string sequence", blocked,
                     SPS_FIXTURE_PHASE_TRACE_VALIDATE);
        free(path);
        return 0;
      }
      for (i = 0; i < blocked->as.sequence.count; ++i) {
        size_t j;
        if (blocked->as.sequence.items[i]->kind != SPSV_NODE_STRING ||
            blocked->as.sequence.items[i]->as.string[0] == '\0' ||
            spsv_utf8_length(blocked->as.sequence.items[i]->as.string) >
                1024) {
          spsv_invalid(actual, "WrongType", path,
                       "blocked_by must contain only strings",
                       blocked->as.sequence.items[i],
                       SPS_FIXTURE_PHASE_TRACE_VALIDATE);
          free(path);
          return 0;
        }
        for (j = 0; j < i; ++j)
          if (strcmp(blocked->as.sequence.items[i]->as.string,
                     blocked->as.sequence.items[j]->as.string) == 0) {
            spsv_invalid(actual, "DuplicateValue", path,
                         "blocked_by values must be unique",
                         blocked->as.sequence.items[i],
                         SPS_FIXTURE_PHASE_TRACE_VALIDATE);
            free(path);
            return 0;
          }
      }
    }
    spsv_invalid(actual, "CaptureUnavailable", path,
                 "a final verification trace requires every capture to be Captured",
                 capture, SPS_FIXTURE_PHASE_TRACE_DERIVE);
    free(path);
    return 0;
  }
  free(path);
  return 1;
}

static int spsv_validate_counterexample(sps_fixture_actual *actual,
                                        const spsv_node *counterexample,
                                        const spsv_node *events,
                                        int *out_validated) {
  static const char *const none_keys[] = {"tag"};
  static const char *const valid_keys[] = {
      "tag", "cause", "first_difference", "pair_sha256", "replay_sha256",
      "validator"};
  static const char *const validator_keys[] = {"id", "build_sha256"};
  const spsv_node *tag, *first, *validator;
  size_t i;
  *out_validated = 0;
  if (!counterexample || counterexample->kind != SPSV_NODE_MAPPING)
    return spsv_invalid(actual, "WrongType", "/decision/counterexample",
                        "counterexample must be a mapping", counterexample,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  tag = spsv_map_get(counterexample, "tag");
  if (!tag || tag->kind != SPSV_NODE_STRING)
    return spsv_invalid(actual, "MissingField",
                        "/decision/counterexample/tag",
                        "counterexample tag is required", counterexample,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  if (strcmp(tag->as.string, "None") == 0)
    return spsv_closed(actual, counterexample, none_keys, 1,
                       "/decision/counterexample");
  if (strcmp(tag->as.string, "Validated") != 0)
    return spsv_invalid(actual, "InvalidEnum",
                        "/decision/counterexample/tag",
                        "counterexample tag must be None or Validated", tag,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  if (!spsv_closed(actual, counterexample, valid_keys, 6,
                   "/decision/counterexample"))
    return 0;
  if (!spsv_map_get(counterexample, "cause") ||
      spsv_map_get(counterexample, "cause")->kind != SPSV_NODE_STRING ||
      !spsv_stable_id_valid(
          spsv_map_get(counterexample, "cause")->as.string) ||
      !spsv_is_sha256(spsv_map_get(counterexample, "pair_sha256")) ||
      !spsv_is_sha256(spsv_map_get(counterexample, "replay_sha256")))
    return spsv_invalid(actual, "InvalidCounterexample",
                        "/decision/counterexample",
                        "validated counterexample requires cause and digests",
                        counterexample, SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  first = spsv_map_get(counterexample, "first_difference");
  if (!spsv_event_valid(actual, first,
                        "/decision/counterexample/first_difference"))
    return 0;
  validator = spsv_map_get(counterexample, "validator");
  if (!validator || validator->kind != SPSV_NODE_MAPPING ||
      !spsv_closed(actual, validator, validator_keys, 2,
                   "/decision/counterexample/validator") ||
      !spsv_map_get(validator, "id") ||
      spsv_map_get(validator, "id")->kind != SPSV_NODE_STRING ||
      !spsv_stable_id_valid(spsv_map_get(validator, "id")->as.string) ||
      !spsv_is_sha256(spsv_map_get(validator, "build_sha256")))
    return spsv_invalid(actual, "InvalidCounterexample",
                        "/decision/counterexample/validator",
                        "validator id and build digest are required", validator,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  for (i = 0; i < events->as.sequence.count; ++i)
    if (spsv_event_equal(first, events->as.sequence.items[i])) {
      *out_validated = 1;
      return 1;
    }
  return spsv_invalid(actual, "UncoveredFirstDifference",
                      "/decision/counterexample/first_difference",
                      "first difference is absent from event_coverage", first,
                      SPS_FIXTURE_PHASE_TRACE_VALIDATE);
}

int spsv_validate_and_derive_trace(sps_fixture_actual *actual) {
  static const char *const root_keys[] = {
      "format", "case", "entry", "authority", "sensitivity", "captures",
      "decision"};
  static const char *const decision_keys[] = {
      "event_coverage", "counterexample", "blockers",
      "all_required_gates_closed", "deployment", "policy"};
  static const char *const blocker_keys[] = {
      "scope", "reason", "source", "detail_sha256"};
  const spsv_node *root = actual->root;
  const spsv_node *format, *case_id, *entry, *authority, *sensitivity;
  const spsv_node *captures, *decision, *events, *counterexample, *blockers;
  const spsv_node *closed, *deployment, *policy;
  int validated = 0;
  int replay_invalidating = 0;
  size_t i;
  if (!root || root->kind != SPSV_NODE_MAPPING)
    return spsv_invalid(actual, "WrongType", "",
                        "trace document root must be a mapping", root,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  if (!spsv_closed(actual, root, root_keys, 7, "")) return 0;
  format = spsv_required(actual, root, "format", SPSV_NODE_STRING, "/format");
  case_id = spsv_required(actual, root, "case", SPSV_NODE_STRING, "/case");
  entry = spsv_required(actual, root, "entry", SPSV_NODE_STRING, "/entry");
  authority =
      spsv_required(actual, root, "authority", SPSV_NODE_STRING, "/authority");
  sensitivity = spsv_required(actual, root, "sensitivity", SPSV_NODE_STRING,
                              "/sensitivity");
  captures =
      spsv_required(actual, root, "captures", SPSV_NODE_MAPPING, "/captures");
  decision =
      spsv_required(actual, root, "decision", SPSV_NODE_MAPPING, "/decision");
  if (!format || !case_id || !entry || !authority || !sensitivity ||
      !captures || !decision)
    return 0;
  if (strcmp(format->as.string, "SPS-Harness-Verification-Trace") != 0)
    return spsv_invalid(actual, "WrongFormat", "/format",
                        "unexpected trace format", format,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  if (!spsv_case_id_valid(case_id->as.string) ||
      !spsv_mlir_symbol_valid(entry->as.string))
    return spsv_invalid(actual, "InvalidIdentifier", "/case",
                        "case or entry does not match its identifier grammar",
                        case_id,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  if (!spsv_string_is(authority, "TestOnly"))
    return spsv_invalid(actual, "WrongAuthority", "/authority",
                        "trace authority must be TestOnly", authority,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  if (!spsv_string_is(sensitivity, "SyntheticTestData") &&
      !spsv_string_is(sensitivity, "Restricted"))
    return spsv_invalid(actual, "InvalidEnum", "/sensitivity",
                        "invalid trace sensitivity", sensitivity,
                        SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  actual->view.sensitivity =
      spsv_string_is(sensitivity, "Restricted")
          ? SPS_FIXTURE_SENSITIVITY_RESTRICTED
          : SPS_FIXTURE_SENSITIVITY_SYNTHETIC_TEST_DATA;
  if (captures->as.mapping.count == 0)
    return spsv_invalid(actual, "MissingCapture", "/captures",
                        "verification trace requires at least one capture",
                        captures, SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  for (i = 0; i < captures->as.mapping.count; ++i)
    if (!spsv_validate_capture(actual, captures->as.mapping.items[i].key,
                               captures->as.mapping.items[i].value))
      return 0;
  if (!spsv_closed(actual, decision, decision_keys, 6, "/decision")) return 0;
  events = spsv_required(actual, decision, "event_coverage",
                         SPSV_NODE_SEQUENCE, "/decision/event_coverage");
  counterexample = spsv_required(actual, decision, "counterexample",
                                 SPSV_NODE_MAPPING,
                                 "/decision/counterexample");
  blockers = spsv_required(actual, decision, "blockers", SPSV_NODE_SEQUENCE,
                           "/decision/blockers");
  closed = spsv_required(actual, decision, "all_required_gates_closed",
                         SPSV_NODE_BOOL,
                         "/decision/all_required_gates_closed");
  deployment = spsv_required(actual, decision, "deployment", SPSV_NODE_STRING,
                             "/decision/deployment");
  policy = spsv_required(actual, decision, "policy", SPSV_NODE_STRING,
                         "/decision/policy");
  if (!events || !counterexample || !blockers || !closed || !deployment ||
      !policy)
    return 0;
  for (i = 0; i < events->as.sequence.count; ++i) {
    char index[64];
    (void)snprintf(index, sizeof(index), "/decision/event_coverage/%zu", i);
    if (!spsv_event_valid(actual, events->as.sequence.items[i], index)) return 0;
    {
      size_t j;
      for (j = 0; j < i; ++j)
        if (spsv_event_equal(events->as.sequence.items[j],
                             events->as.sequence.items[i]))
          return spsv_invalid(actual, "DuplicateEvent", index,
                              "event selectors must be unique",
                              events->as.sequence.items[i],
                              SPS_FIXTURE_PHASE_TRACE_VALIDATE);
    }
  }
  if (!spsv_validate_counterexample(actual, counterexample, events,
                                    &validated))
    return 0;
  for (i = 0; i < blockers->as.sequence.count; ++i) {
    const spsv_node *blocker = blockers->as.sequence.items[i];
    const spsv_node *scope, *reason, *source, *digest;
    if (!blocker || blocker->kind != SPSV_NODE_MAPPING ||
        !spsv_closed(actual, blocker, blocker_keys, 4,
                     "/decision/blockers"))
      return spsv_invalid(actual, "InvalidBlocker", "/decision/blockers",
                          "blocker must be a closed mapping", blocker,
                          SPS_FIXTURE_PHASE_TRACE_VALIDATE);
    scope = spsv_map_get(blocker, "scope");
    reason = spsv_map_get(blocker, "reason");
    source = spsv_map_get(blocker, "source");
    digest = spsv_map_get(blocker, "detail_sha256");
    if (!scope || scope->kind != SPSV_NODE_STRING || !reason ||
        reason->kind != SPSV_NODE_STRING || !source ||
        source->kind != SPSV_NODE_STRING ||
        !spsv_stable_id_valid(reason->as.string) ||
        !spsv_stable_id_valid(source->as.string) ||
        (digest && !spsv_is_sha256(digest)))
      return spsv_invalid(actual, "InvalidBlocker", "/decision/blockers",
                          "blocker scope, reason, source, and digest are invalid",
                          blocker, SPS_FIXTURE_PHASE_TRACE_VALIDATE);
    {
      size_t j;
      for (j = 0; j < i; ++j)
        if (spsv_node_equal(blockers->as.sequence.items[j], blocker))
          return spsv_invalid(actual, "DuplicateBlocker",
                              "/decision/blockers",
                              "blockers must be unique", blocker,
                              SPS_FIXTURE_PHASE_TRACE_VALIDATE);
    }
    if (strcmp(scope->as.string, "ReplayInvalidating") == 0)
      replay_invalidating = 1;
    else if (strcmp(scope->as.string, "RunFinalization") == 0)
      return spsv_invalid(actual, "RunNotFinal",
                          "/decision/blockers",
                          "run-finalization blocker prevents comparison",
                          blocker, SPS_FIXTURE_PHASE_TRACE_DERIVE);
    else if (strcmp(scope->as.string, "ProofCompletion") != 0)
      return spsv_invalid(actual, "InvalidEnum", "/decision/blockers",
                          "unknown blocker scope", scope,
                          SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  }
  if (closed->as.boolean && blockers->as.sequence.count)
    return spsv_invalid(actual, "ConflictingDecision",
                        "/decision/all_required_gates_closed",
                        "closed gates cannot coexist with blockers", closed,
                        SPS_FIXTURE_PHASE_TRACE_DERIVE);
  if (strcmp(deployment->as.string, "Open") != 0 ||
      !spsv_policy_valid(policy->as.string))
    return spsv_invalid(actual, "InvalidFinalAxis", "/decision",
                        "deployment must be Open and policy must be modeled",
                        decision, SPS_FIXTURE_PHASE_TRACE_VALIDATE);
  if (validated && replay_invalidating)
    return spsv_invalid(actual, "ConflictingDecision",
                        "/decision/counterexample",
                        "validated counterexample conflicts with replay blocker",
                        counterexample, SPS_FIXTURE_PHASE_TRACE_DERIVE);
  if (!validated && replay_invalidating)
    return spsv_invalid(actual, "ReplayInvalidWithoutCounterexample",
                        "/decision/blockers",
                        "ReplayInvalidating cannot derive Unknown without a candidate counterexample",
                        blockers, SPS_FIXTURE_PHASE_TRACE_DERIVE);
  actual->captures = (spsv_node *)captures;
  actual->event_coverage = (spsv_node *)events;
  actual->view.case_id = spsv_text_view(case_id->as.string);
  actual->view.entry = spsv_text_view(entry->as.string);
  actual->view.position.deployment = spsv_text_view(deployment->as.string);
  actual->view.position.policy = spsv_text_view(policy->as.string);
  if (validated) {
    const spsv_node *first = spsv_map_get(counterexample, "first_difference");
    const spsv_node *id = spsv_map_get(first, "id");
    actual->view.position.tag = SPS_FIXTURE_POSITION_COUNTEREXAMPLE;
    actual->view.position.detail.counterexample.cause =
        spsv_text_view(spsv_map_get(counterexample, "cause")->as.string);
    actual->view.position.detail.counterexample.first_difference.kind =
        spsv_text_view(spsv_map_get(first, "kind")->as.string);
    actual->view.position.detail.counterexample.first_difference.field =
        spsv_text_view(spsv_map_get(first, "field")->as.string);
    actual->view.position.detail.counterexample.first_difference.id =
        spsv_text_view(id ? id->as.string : "");
  } else if (blockers->as.sequence.count) {
    const spsv_node *reason;
    actual->view.position.tag = SPS_FIXTURE_POSITION_UNKNOWN;
    if (blockers->as.sequence.count == 1) {
      reason =
          spsv_map_get(blockers->as.sequence.items[0], "reason");
      actual->view.position.detail.unknown.reason =
          spsv_text_view(reason->as.string);
    } else {
      actual->derived_reason = spsv_strdup("OpenModelObligations");
      if (!actual->derived_reason) return 0;
      actual->view.position.detail.unknown.reason =
          spsv_text_view(actual->derived_reason);
    }
  } else if (closed->as.boolean) {
    if (events->as.sequence.count == 0)
      return spsv_invalid(actual, "MissingEventCoverage",
                          "/decision/event_coverage",
                          "Proved test outcome requires event coverage", events,
                          SPS_FIXTURE_PHASE_TRACE_DERIVE);
    actual->view.position.tag = SPS_FIXTURE_POSITION_PROVED;
  } else {
    return spsv_invalid(actual, "MissingDecisionEvidence", "/decision",
                        "trace derives neither Counterexample, Unknown, nor Proved",
                        decision, SPS_FIXTURE_PHASE_TRACE_DERIVE);
  }
  return 1;
}
