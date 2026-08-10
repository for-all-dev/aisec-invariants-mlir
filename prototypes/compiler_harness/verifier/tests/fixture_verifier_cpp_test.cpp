#include "sps_harness/fixture_verifier.hpp"

#include <cassert>
#include <string>

#define H64 "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

int main() {
  const std::string trace =
      "format: SPS-Harness-Verification-Trace\n"
      "case: cpp/good\nentry: cpp_good\nauthority: TestOnly\n"
      "sensitivity: SyntheticTestData\n"
      "captures:\n  shape:\n    state: Captured\n    kind: mlir\n"
      "    extractor: structure\n    endpoint_sha256: " H64 "\n"
      "    facts: {operation.names: [llvm.return]}\n"
      "decision:\n"
      "  event_coverage: [{kind: Output, field: valueBytes}]\n"
      "  counterexample: {tag: None}\n  blockers: []\n"
      "  all_required_gates_closed: true\n"
      "  deployment: Open\n  policy: Complete\n";
  const std::string snapshot =
      "format: SPS-Harness-Fixture-Snapshot\n"
      "case: cpp/good\nentry: cpp_good\n"
      "expect:\n  position: {tag: Proved}\n"
      "  deployment: Open\n  policy: Complete\n"
      "  events: [{kind: Output, field: valueBytes}]\n"
      "  pipelines:\n"
      "    shape:\n"
      "      kind: mlir\n"
      "      properties:\n"
      "        operation.names: {contains: [llvm.return]}\n"
      "because: wrapper smoke test\n";
  auto actual =
      sps::harness::actual::derive(sps::harness::bytes_view(trace));
  assert(actual.valid());
  assert(actual.native_handle() != nullptr);
  assert(actual.view().sensitivity ==
         SPS_FIXTURE_SENSITIVITY_SYNTHETIC_TEST_DATA);
  assert(actual.event_count() == 1);
  assert(sps::harness::as_string_view(actual.event(0).kind) == "Output");
  auto result =
      sps::harness::compare(actual, sps::harness::bytes_view(snapshot));
  assert(result.comparison() == SPS_FIXTURE_COMPARISON_MATCHED);
  assert(result.native_handle() != nullptr);
  assert(result.pipeline_count() == 1);
  assert(sps::harness::as_string_view(result.pipeline(0).pipeline) == "shape");
  assert(result.consumption_count() > 0);
  assert(result.issue_count() == 0);
  auto json = result.json();
  assert(json.find("\"outcome\":{\"tag\":\"Matched\"") != std::string::npos);
  assert(json.empty() || json.back() != '\0');
}
