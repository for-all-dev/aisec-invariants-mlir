#include "sps_harness/fixture_verifier.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define H64 "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

static const char proved_trace[] =
    "format: SPS-Harness-Verification-Trace\n"
    "case: loop/good\n"
    "entry: loop_good\n"
    "authority: TestOnly\n"
    "sensitivity: SyntheticTestData\n"
    "captures:\n"
    "  shape:\n"
    "    state: Captured\n"
    "    kind: mlir\n"
    "    extractor: mlir-structure\n"
    "    endpoint_sha256: " H64 "\n"
    "    facts:\n"
    "      operation.names: [llvm.add, llvm.return]\n"
    "decision:\n"
    "  event_coverage:\n"
    "    - {kind: Output, field: valueBytes, id: result}\n"
    "  counterexample: {tag: None}\n"
    "  blockers: []\n"
    "  all_required_gates_closed: true\n"
    "  deployment: Open\n"
    "  policy: Complete\n";

static const char proved_snapshot[] =
    "format: SPS-Harness-Fixture-Snapshot\n"
    "case: loop/good\n"
    "entry: loop_good\n"
    "expect:\n"
    "  position: {tag: Proved}\n"
    "  deployment: Open\n"
    "  policy: Complete\n"
    "  events:\n"
    "    - {kind: Output, field: valueBytes, id: result}\n"
    "  pipelines:\n"
    "    shape:\n"
    "      kind: mlir\n"
    "      properties:\n"
    "        operation.names:\n"
    "          contains: [llvm.return]\n"
    "          excludes: [llvm.udiv]\n"
    "          ordered: [llvm.add, llvm.return]\n"
    "          count: {min: 2, max: 2}\n"
    "because: public loop bounds close every required check\n";

static const char mismatch_snapshot[] =
    "format: SPS-Harness-Fixture-Snapshot\n"
    "case: loop/good\n"
    "entry: loop_good\n"
    "expect:\n"
    "  position: {tag: Unknown, reason: SolverTimeout}\n"
    "  deployment: Open\n"
    "  policy: Complete\n"
    "  events:\n"
    "    - {kind: Output, field: valueBytes, id: result}\n"
    "  pipelines:\n"
    "    shape:\n"
    "      kind: mlir\n"
    "      properties:\n"
    "        operation.names: {contains: [llvm.return]}\n"
    "because: expectation mutation must not change derivation\n";

static const char unknown_trace[] =
    "format: SPS-Harness-Verification-Trace\n"
    "case: solver/timeout\nentry: solver_timeout\n"
    "authority: TestOnly\nsensitivity: SyntheticTestData\n"
    "captures:\n"
    "  shape:\n"
    "    state: Captured\n    kind: mlir\n    extractor: e1\n"
    "    endpoint_sha256: " H64 "\n"
    "    facts:\n"
    "      operation.names: [llvm.return]\n"
    "      plain.yes: yes\n"
    "      plain.on: on\n"
    "      typed.bool: true\n"
    "      quoted.bool: \"true\"\n"
    "      string.dot: .1abc\n"
    "      string.plus: +1abc\n"
    "decision:\n"
    "  event_coverage: []\n"
    "  counterexample: {tag: None}\n"
    "  blockers:\n"
    "    - {scope: ProofCompletion, reason: SolverTimeout, source: audit-all}\n"
    "  all_required_gates_closed: false\n"
    "  deployment: Open\n  policy: Incomplete\n";

static const char unknown_snapshot[] =
    "format: SPS-Harness-Fixture-Snapshot\n"
    "case: solver/timeout\nentry: solver_timeout\n"
    "expect:\n"
    "  position: {tag: Unknown, reason: SolverTimeout}\n"
    "  deployment: Open\n  policy: Incomplete\n"
    "  events: []\n"
    "  pipelines:\n"
    "    shape:\n"
    "      kind: mlir\n"
    "      properties:\n"
    "        operation.names: {equals: [llvm.return]}\n"
    "because: the solver did not close the proof-completion gate\n";

static const char counterexample_trace[] =
    "format: SPS-Harness-Verification-Trace\n"
    "case: output/leak\nentry: output_leak\n"
    "authority: TestOnly\nsensitivity: SyntheticTestData\n"
    "captures:\n"
    "  shape:\n"
    "    state: Captured\n    kind: mlir\n    extractor: structure\n"
    "    endpoint_sha256: " H64 "\n"
    "    facts: {operation.names: [llvm.store, llvm.return]}\n"
    "decision:\n"
    "  event_coverage:\n"
    "    - {kind: Output, field: valueBytes, id: public-output}\n"
    "  counterexample:\n"
    "    tag: Validated\n"
    "    cause: PublicOutputMismatch\n"
    "    first_difference: {kind: Output, field: valueBytes, id: public-output}\n"
    "    pair_sha256: " H64 "\n"
    "    replay_sha256: " H64 "\n"
    "    validator: {id: relation-reference, build_sha256: " H64 "}\n"
    "  blockers: []\n"
    "  all_required_gates_closed: false\n"
    "  deployment: Open\n  policy: Findings\n";

static const char counterexample_snapshot[] =
    "format: SPS-Harness-Fixture-Snapshot\n"
    "case: output/leak\nentry: output_leak\n"
    "expect:\n"
    "  position:\n"
    "    tag: Counterexample\n"
    "    cause: PublicOutputMismatch\n"
    "    first_difference: {kind: Output, field: valueBytes, id: public-output}\n"
    "  deployment: Open\n  policy: Findings\n"
    "  events:\n"
    "    - {kind: Output, field: valueBytes, id: public-output}\n"
    "  pipelines:\n"
    "    shape:\n"
    "      kind: mlir\n"
    "      properties:\n"
    "        operation.names: {ordered: [llvm.store, llvm.return]}\n"
    "because: independently replayed lanes differ at the public output\n";

static int bytes_contains(const char *haystack, size_t haystack_size,
                          const char *needle) {
  size_t i, needle_size = strlen(needle);
  if (needle_size > haystack_size) return 0;
  for (i = 0; i + needle_size <= haystack_size; ++i)
    if (memcmp(haystack + i, needle, needle_size) == 0) return 1;
  return 0;
}

static void expect_comparison(const char *snapshot,
                              sps_fixture_comparison expected) {
  sps_fixture_actual *actual = NULL;
  sps_fixture_result *result = NULL;
  sps_fixture_actual_view actual_view;
  sps_fixture_result_view result_view;
  size_t required = 0;
  char *json;
  assert(sps_fixture_derive_trace((const uint8_t *)proved_trace,
                                  strlen(proved_trace), &actual) ==
         SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_actual_get_view(actual, &actual_view) ==
         SPS_FIXTURE_STATUS_OK);
  assert(actual_view.state == SPS_FIXTURE_ACTUAL_DERIVED);
  assert(actual_view.position.tag == SPS_FIXTURE_POSITION_PROVED);
  assert(sps_fixture_compare_snapshot(actual, (const uint8_t *)snapshot,
                                      strlen(snapshot), &result) ==
         SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_result_get_view(result, &result_view) ==
         SPS_FIXTURE_STATUS_OK);
  if (result_view.comparison != expected) {
    size_t i;
    for (i = 0; i < sps_fixture_result_issue_count(result); ++i) {
      sps_fixture_issue_view issue;
      assert(sps_fixture_result_issue_at(result, i, &issue) ==
             SPS_FIXTURE_STATUS_OK);
      fprintf(stderr, "unexpected result issue: %.*s at %.*s\n",
              (int)issue.message.size, issue.message.data,
              (int)issue.path.size, issue.path.data);
    }
  }
  assert(result_view.comparison == expected);
  assert(sps_fixture_result_write_json(result, NULL, 0, &required) ==
         SPS_FIXTURE_STATUS_BUFFER_TOO_SMALL);
  assert(required > 0);
  json = (char *)malloc(required);
  assert(json);
  assert(sps_fixture_result_write_json(result, json, required, &required) ==
         SPS_FIXTURE_STATUS_OK);
  assert(memchr(json, '\0', required) == NULL);
  assert(bytes_contains(json, required, "\"authority\":\"TestOnly\""));
  free(json);
  sps_fixture_result_destroy(result);
  sps_fixture_actual_destroy(actual);
}

static void invalid_trace(const char *trace) {
  sps_fixture_actual *actual = NULL;
  sps_fixture_actual_view view;
  assert(sps_fixture_derive_trace((const uint8_t *)trace, strlen(trace),
                                  &actual) == SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_actual_get_view(actual, &view) == SPS_FIXTURE_STATUS_OK);
  assert(view.state == SPS_FIXTURE_ACTUAL_INVALID);
  assert(sps_fixture_actual_issue_count(actual) > 0);
  sps_fixture_actual_destroy(actual);
}

static void empty_inputs_are_invalid_wire(void) {
  sps_fixture_actual *empty_actual = NULL;
  sps_fixture_actual *valid_actual = NULL;
  sps_fixture_result *empty_snapshot_result = NULL;
  sps_fixture_actual_view actual_view;
  sps_fixture_result_view result_view;
  assert(sps_fixture_derive_trace(NULL, 0, &empty_actual) ==
         SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_actual_get_view(empty_actual, &actual_view) ==
         SPS_FIXTURE_STATUS_OK);
  assert(actual_view.state == SPS_FIXTURE_ACTUAL_INVALID);
  assert(sps_fixture_actual_issue_count(empty_actual) > 0);

  assert(sps_fixture_derive_trace((const uint8_t *)proved_trace,
                                  strlen(proved_trace), &valid_actual) ==
         SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_compare_snapshot(valid_actual, NULL, 0,
                                      &empty_snapshot_result) ==
         SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_result_get_view(empty_snapshot_result, &result_view) ==
         SPS_FIXTURE_STATUS_OK);
  assert(result_view.comparison == SPS_FIXTURE_COMPARISON_INVALID);
  assert(sps_fixture_result_issue_count(empty_snapshot_result) > 0);

  sps_fixture_result_destroy(empty_snapshot_result);
  sps_fixture_actual_destroy(valid_actual);
  sps_fixture_actual_destroy(empty_actual);
}

static void invalid_plain_scalar(const char *scalar) {
  char trace[2048];
  int written = snprintf(
      trace, sizeof(trace),
      "format: SPS-Harness-Verification-Trace\n"
      "case: invalid/scalar\nentry: invalid_scalar\n"
      "authority: TestOnly\nsensitivity: SyntheticTestData\n"
      "captures:\n"
      "  shape: {state: Captured, kind: mlir, extractor: structure, "
      "endpoint_sha256: " H64 ", facts: {n: %s}}\n"
      "decision: {event_coverage: [{kind: Output, field: valueBytes}], "
      "counterexample: {tag: None}, blockers: [], "
      "all_required_gates_closed: true, deployment: Open, policy: Complete}\n",
      scalar);
  assert(written > 0 && (size_t)written < sizeof(trace));
  invalid_trace(trace);
}

static void expect_pair(const char *trace, const char *snapshot,
                        sps_fixture_position_tag position) {
  sps_fixture_actual *actual = NULL;
  sps_fixture_result *result = NULL;
  sps_fixture_actual_view actual_view;
  sps_fixture_result_view result_view;
  assert(sps_fixture_derive_trace((const uint8_t *)trace, strlen(trace),
                                  &actual) == SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_actual_get_view(actual, &actual_view) ==
         SPS_FIXTURE_STATUS_OK);
  assert(actual_view.state == SPS_FIXTURE_ACTUAL_DERIVED);
  assert(actual_view.position.tag == position);
  assert(sps_fixture_compare_snapshot(actual, (const uint8_t *)snapshot,
                                      strlen(snapshot), &result) ==
         SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_result_get_view(result, &result_view) ==
         SPS_FIXTURE_STATUS_OK);
  assert(result_view.comparison == SPS_FIXTURE_COMPARISON_MATCHED);
  sps_fixture_result_destroy(result);
  sps_fixture_actual_destroy(actual);
}

static void invalid_snapshot(const char *snapshot) {
  sps_fixture_actual *actual = NULL;
  sps_fixture_result *result = NULL;
  sps_fixture_result_view view;
  assert(sps_fixture_derive_trace((const uint8_t *)proved_trace,
                                  strlen(proved_trace), &actual) ==
         SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_compare_snapshot(actual, (const uint8_t *)snapshot,
                                      strlen(snapshot), &result) ==
         SPS_FIXTURE_STATUS_OK);
  assert(sps_fixture_result_get_view(result, &view) == SPS_FIXTURE_STATUS_OK);
  assert(view.comparison == SPS_FIXTURE_COMPARISON_INVALID);
  assert(sps_fixture_result_issue_count(result) > 0);
  sps_fixture_result_destroy(result);
  sps_fixture_actual_destroy(actual);
}

int main(void) {
  empty_inputs_are_invalid_wire();
  expect_comparison(proved_snapshot, SPS_FIXTURE_COMPARISON_MATCHED);
  expect_comparison(mismatch_snapshot, SPS_FIXTURE_COMPARISON_MISMATCHED);
  expect_pair(unknown_trace, unknown_snapshot, SPS_FIXTURE_POSITION_UNKNOWN);
  expect_pair(counterexample_trace, counterexample_snapshot,
              SPS_FIXTURE_POSITION_COUNTEREXAMPLE);
  invalid_trace(
      "format: SPS-Harness-Verification-Trace\n"
      "format: duplicate\n");
  invalid_trace(
      "format: SPS-Harness-Verification-Trace\n"
      "case: x\nentry: x\nauthority: TestOnly\n"
      "sensitivity: SyntheticTestData\ncaptures: {}\n"
      "decision: {event_coverage: [], counterexample: {tag: None}, "
      "blockers: [], all_required_gates_closed: false, deployment: Open, "
      "policy: Complete}\n");
  invalid_trace(
      "format: SPS-Harness-Verification-Trace\n"
      "case: invalid/failure\nentry: invalid_failure\n"
      "authority: TestOnly\nsensitivity: SyntheticTestData\n"
      "captures:\n"
      "  shape: {state: ProducerFailed, kind: mlir, extractor: build, error: failed}\n"
      "decision: {event_coverage: [], counterexample: {tag: None}, "
      "blockers: [{scope: ProofCompletion, reason: BuildFailed, source: build}], "
      "all_required_gates_closed: false, deployment: Open, policy: Incomplete}\n");
  invalid_trace(
      "format: SPS-Harness-Verification-Trace\n"
      "case: invalid/facts\nentry: invalid_facts\n"
      "authority: TestOnly\nsensitivity: SyntheticTestData\n"
      "captures:\n"
      "  shape:\n"
      "    state: Captured\n    kind: mlir\n    extractor: structure\n"
      "    endpoint_sha256: " H64 "\n"
      "    facts: {nested: {expected-result: copied}}\n"
      "decision: {event_coverage: [{kind: Output, field: valueBytes}], "
      "counterexample: {tag: None}, blockers: [], "
      "all_required_gates_closed: true, deployment: Open, policy: Complete}\n");
  invalid_trace(
      "format: SPS-Harness-Verification-Trace\n"
      "case: invalid/matching-fact\nentry: invalid_matching_fact\n"
      "authority: TestOnly\nsensitivity: SyntheticTestData\n"
      "captures:\n"
      "  shape:\n"
      "    state: Captured\n    kind: mlir\n    extractor: structure\n"
      "    endpoint_sha256: " H64 "\n"
      "    facts: {nested: {matching-details: precompared}}\n"
      "decision: {event_coverage: [{kind: Output, field: valueBytes}], "
      "counterexample: {tag: None}, blockers: [], "
      "all_required_gates_closed: true, deployment: Open, policy: Complete}\n");
  invalid_plain_scalar("-0");
  invalid_plain_scalar("+1");
  invalid_plain_scalar("01");
  invalid_plain_scalar("1_0");
  invalid_plain_scalar("0x1");
  invalid_plain_scalar("-0x1");
  invalid_plain_scalar("1:2");
  invalid_plain_scalar(".5");
  invalid_plain_scalar("-.5");
  invalid_plain_scalar("+.inf");
  invalid_plain_scalar("-.NaN");
  invalid_plain_scalar("1e2");
  invalid_plain_scalar("9223372036854775808");
  invalid_trace(
      "format: SPS-Harness-Verification-Trace\n"
      "case: invalid/replay-blocker\nentry: invalid_replay_blocker\n"
      "authority: TestOnly\nsensitivity: SyntheticTestData\n"
      "captures:\n"
      "  shape: {state: Captured, kind: mlir, extractor: structure, "
      "endpoint_sha256: " H64 ", facts: {x: 1}}\n"
      "decision: {event_coverage: [], counterexample: {tag: None}, "
      "blockers: [{scope: ReplayInvalidating, reason: ReplayFailed, source: replay}], "
      "all_required_gates_closed: false, deployment: Open, policy: Incomplete}\n");
  invalid_trace(
      "format: SPS-Harness-Verification-Trace\n"
      "case: invalid/event\nentry: invalid_event\n"
      "authority: TestOnly\nsensitivity: SyntheticTestData\n"
      "captures:\n"
      "  shape: {state: Captured, kind: mlir, extractor: structure, "
      "endpoint_sha256: " H64 ", facts: {x: 1}}\n"
      "decision: {event_coverage: [{kind: Output, field: configuredClass}], "
      "counterexample: {tag: None}, blockers: [], "
      "all_required_gates_closed: true, deployment: Open, policy: Complete}\n");
  invalid_trace(
      "format: SPS-Harness-Verification-Trace\n"
      "case: invalid/scalar\nentry: invalid_scalar\n"
      "authority: TestOnly\nsensitivity: SyntheticTestData\n"
      "captures:\n"
      "  shape: {state: Captured, kind: mlir, extractor: structure, "
      "endpoint_sha256: " H64 ", facts: {n: 9223372036854775808}}\n"
      "decision: {event_coverage: [{kind: Output, field: valueBytes}], "
      "counterexample: {tag: None}, blockers: [], "
      "all_required_gates_closed: true, deployment: Open, policy: Complete}\n");
  invalid_snapshot(
      "format: SPS-Harness-Fixture-Snapshot\n"
      "case: loop/good\nentry: loop_good\n"
      "expect: {position: {tag: Proved}, deployment: Open, policy: Complete, "
      "events: [{kind: Output, field: valueBytes, id: result}], "
      "pipelines: {shape: {kind: mlir, properties: {}}}}\n"
      "because: empty properties are invalid\n");
  invalid_snapshot(
      "format: SPS-Harness-Fixture-Snapshot\n"
      "case: loop/good\nentry: loop_good\n"
      "expect: {position: {tag: Proved}, deployment: Open, policy: Complete, "
      "events: [{kind: Output, field: valueBytes, id: result}], "
      "pipelines: {shape: {kind: mlir, properties: {operation.names: "
      "{count: {eq: 2, min: 1}}}}}}\n"
      "because: mixed count modes are invalid\n");
  invalid_snapshot(
      "format: SPS-Harness-Fixture-Snapshot\n"
      "case: loop/good\nentry: loop_good\n"
      "expect: {position: {tag: Proved}, deployment: Open, policy: Complete, "
      "events: [{kind: Output, field: valueBytes, id: result}], "
      "pipelines: {shape: {kind: mlir, properties: {operation.names: "
      "{count: {min: 3, max: 2}}}}}}\n"
      "because: schema-valid crossed bounds fail semantic validation\n");
  puts("fixture_verifier_test: PASS");
  return 0;
}
