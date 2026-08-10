#!/usr/bin/env python3
"""End-to-end contract for the host fixture-verifier CLI."""

from __future__ import annotations

import json
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator


H64 = "0123456789abcdef" * 4
LONG_FACT_KEY = "k" * 256


def trace(sensitivity: str = "SyntheticTestData") -> str:
    return f"""\
format: SPS-Harness-Verification-Trace
case: cli/loop-good
entry: loop_good
authority: TestOnly
sensitivity: {sensitivity}
captures:
  shape:
    state: Captured
    kind: mlir
    extractor: mlir-structure
    endpoint_sha256: {H64}
    facts:
      operation.names: [llvm.add, llvm.return]
      {LONG_FACT_KEY}: boundary
decision:
  event_coverage:
    - {{kind: Output, field: valueBytes, id: result}}
  counterexample: {{tag: None}}
  blockers: []
  all_required_gates_closed: true
  deployment: Open
  policy: Complete
"""


MATCHED_SNAPSHOT = """\
format: SPS-Harness-Fixture-Snapshot
case: cli/loop-good
entry: loop_good
expect:
  position: {tag: Proved}
  deployment: Open
  policy: Complete
  events:
    - {kind: Output, field: valueBytes, id: result}
  pipelines:
    shape:
      kind: mlir
      properties:
        operation.names:
          contains: [llvm.return]
          excludes: [llvm.udiv]
          ordered: [llvm.add, llvm.return]
          count: {eq: 2}
        LONG_FACT_KEY: {equals: boundary}
because: the complete expectation-blind trace closes the modeled fixture gates
"""
MATCHED_SNAPSHOT = MATCHED_SNAPSHOT.replace("LONG_FACT_KEY", LONG_FACT_KEY)


MISMATCHED_SNAPSHOT = MATCHED_SNAPSHOT.replace(
    "position: {tag: Proved}",
    "position: {tag: Unknown, reason: SolverTimeout}",
)


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def invoke(cli: Path, trace_path: Path, snapshot_path: Path, *extra: str):
    return subprocess.run(
        [
            str(cli),
            "--trace",
            str(trace_path),
            "--snapshot",
            str(snapshot_path),
            *extra,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def decode_stdout(run: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert run.stdout.endswith("\n"), run.stdout
    return json.loads(run.stdout)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: fixture_verifier_cli_test.py CLI SCHEMA_DIR")
    cli = Path(sys.argv[1]).resolve()
    schema_dir = Path(sys.argv[2]).resolve()
    assert cli.is_file(), cli
    result_schema = json.loads(
        (schema_dir / "SPS-Harness-Verification-Result.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(result_schema)
    result_validator = Draft202012Validator(result_schema)

    def validate_result(value: dict[str, object]) -> None:
        errors = sorted(
            result_validator.iter_errors(value),
            key=lambda error: list(error.path),
        )
        assert not errors, [error.message for error in errors]

    with tempfile.TemporaryDirectory(prefix="sps-fixture-verifier-") as directory:
        root = Path(directory)
        trace_path = root / "trace.yaml"
        snapshot_path = root / "snapshot.yaml"
        write(trace_path, trace())
        write(snapshot_path, MATCHED_SNAPSHOT)

        untrusted_synthetic = invoke(cli, trace_path, snapshot_path)
        assert untrusted_synthetic.returncode == 2
        assert untrusted_synthetic.stdout == ""
        assert "--allow-synthetic-test-data" in untrusted_synthetic.stderr

        matched = invoke(
            cli,
            trace_path,
            snapshot_path,
            "--allow-synthetic-test-data",
        )
        assert matched.returncode == 0, (matched.returncode, matched.stderr)
        matched_result = decode_stdout(matched)
        validate_result(matched_result)
        assert matched_result["outcome"]["tag"] == "Matched"
        assert matched_result["authority"] == "TestOnly"
        assert matched_result["claimable"] is False
        assert matched_result["sps_model_status"] == "NotComputed"
        assert matched_result["sensitivity"] == "SyntheticTestData"
        assert matched_result["ignored"] == [
            {"path": "/because", "reason": "ExplanationOnly"}
        ]
        long_row = next(
            row
            for row in matched_result["consumed"]
            if row["expectation_path"].endswith(f"/{LONG_FACT_KEY}/equals")
        )
        assert long_row["expectation_path"] == (
            f"/expect/pipelines/shape/properties/{LONG_FACT_KEY}/equals"
        )
        assert long_row["actual_path"] == f"/captures/shape/facts/{LONG_FACT_KEY}"

        write(snapshot_path, MISMATCHED_SNAPSHOT)
        mismatched = invoke(
            cli,
            trace_path,
            snapshot_path,
            "--allow-synthetic-test-data",
        )
        assert mismatched.returncode == 1, (
            mismatched.returncode,
            mismatched.stderr,
        )
        mismatch_result = decode_stdout(mismatched)
        validate_result(mismatch_result)
        assert mismatch_result["outcome"]["tag"] == "Mismatched"
        assert any(
            row["expectation_path"] == "/expect/position/reason"
            and row["actual"] == {"state": "Missing"}
            for row in mismatch_result["consumed"]
        )

        # Restricted details never go to stdout. The explicit destination is
        # newly created with owner-only permissions and is never overwritten.
        write(trace_path, trace("Restricted"))
        refused = invoke(cli, trace_path, snapshot_path)
        assert refused.returncode == 2
        assert refused.stdout == ""
        assert "refusing stdout" in refused.stderr

        restricted_result_path = root / "restricted-result.json"
        restricted = invoke(
            cli,
            trace_path,
            snapshot_path,
            "--restricted-output",
            str(restricted_result_path),
        )
        assert restricted.returncode == 1, (restricted.returncode, restricted.stderr)
        assert restricted.stdout == ""
        restricted_result = json.loads(
            restricted_result_path.read_text(encoding="utf-8")
        )
        validate_result(restricted_result)
        assert restricted_result["sensitivity"] == "Restricted"
        mode = stat.S_IMODE(restricted_result_path.stat().st_mode)
        assert mode == stat.S_IRUSR | stat.S_IWUSR, oct(mode)

        second_write = invoke(
            cli,
            trace_path,
            snapshot_path,
            "--restricted-output",
            str(restricted_result_path),
        )
        assert second_write.returncode == 2
        assert restricted_result_path.read_text(encoding="utf-8").endswith("\n")

        # Invalid trace diagnostics are fail-closed as Restricted and retain
        # exit status 2 when routed to an explicit protected destination.
        invalid_trace_path = root / "invalid-trace.yaml"
        write(invalid_trace_path, "")
        invalid_result_path = root / "invalid-result.json"
        invalid = invoke(
            cli,
            invalid_trace_path,
            snapshot_path,
            "--restricted-output",
            str(invalid_result_path),
        )
        assert invalid.returncode == 2, (invalid.returncode, invalid.stderr)
        invalid_result = json.loads(invalid_result_path.read_text(encoding="utf-8"))
        validate_result(invalid_result)
        assert invalid_result["outcome"]["tag"] == "Invalid"
        assert invalid_result["sensitivity"] == "Restricted"
        assert invalid_result["issues"]

    print("fixture verifier CLI contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
