#!/usr/bin/env python3
"""Adversarial unit coverage for the expectation-blind trace assembler."""

from __future__ import annotations

import copy
import itertools
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import yaml


def fragment(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": "SPS-Harness-Trace-Fragment",
        "session": "test-session",
        "case": "contract/demo",
        "entry": "demo",
        "record": record,
    }


def expect_error(call: Callable[[], Any], text: str) -> None:
    try:
        call()
    except fixture_trace.TraceError as error:
        assert text in str(error), (text, str(error))
    else:
        raise AssertionError(f"expected TraceError containing {text!r}")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fixture_trace_test.py TOOLS")
    tools = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(tools))
    global fixture_trace
    import fixture_trace

    digest_a = "a" * 64
    digest_b = "b" * 64
    event = {"kind": "Output", "field": "valueBytes", "id": "public-output"}
    records = [
        fragment(
            {
                "tag": "PipelineCapture",
                "pipeline": "modeled-shape",
                "capture": {
                    "state": "Captured",
                    "kind": "mlir",
                    "extractor": "mlir-structure-v1",
                    "endpoint_sha256": digest_a,
                    "facts": {
                        "operation.names": ["llvm.store", "llvm.return"],
                        "operation.count": 2,
                    },
                },
            }
        ),
        fragment(
            {
                "tag": "PipelineCapture",
                "pipeline": "candidate-bytes",
                "capture": {
                    "state": "Blocked",
                    "kind": "bytes",
                    "extractor": "exact-bytes-v1",
                    "error": "upstream artifact unavailable",
                    "blocked_by": ["compile"],
                },
            }
        ),
        fragment(
            {
                "tag": "RequiredChecks",
                "event_coverage": [event],
                "all_required_gates_closed": False,
            }
        ),
        fragment(
            {
                "tag": "ValidatedCounterexample",
                "counterexample": {
                    "tag": "Validated",
                    "cause": "ProjectedPayloadMismatch",
                    "first_difference": event,
                    "pair_sha256": digest_a,
                    "replay_sha256": digest_b,
                    "validator": {
                        "id": "relation-reference-runner",
                        "build_sha256": digest_a,
                    },
                },
            }
        ),
        fragment(
            {
                "tag": "Blocker",
                "blocker": {
                    "scope": "ProofCompletion",
                    "reason": "SolverTimeout",
                    "source": "audit-all",
                    "detail_sha256": digest_b,
                },
            }
        ),
        fragment({"tag": "FinalAxes", "deployment": "Open", "policy": "Complete"}),
    ]

    def assemble(rows: Any) -> dict[str, Any]:
        return fixture_trace.assemble_fragments(
            rows, sensitivity="SyntheticTestData"
        )

    trace = assemble(records)
    assert list(trace) == [
        "format",
        "case",
        "entry",
        "authority",
        "sensitivity",
        "captures",
        "decision",
    ]
    assert trace["format"] == "SPS-Harness-Verification-Trace"
    assert trace["authority"] == "TestOnly"
    assert trace["sensitivity"] == "SyntheticTestData"
    assert list(trace["captures"]) == ["candidate-bytes", "modeled-shape"]
    assert list(trace["captures"]["modeled-shape"]["facts"]) == [
        "operation.count",
        "operation.names",
    ]
    assert trace["decision"]["counterexample"]["tag"] == "Validated"
    assert trace["decision"]["event_coverage"] == [event]
    assert "session" not in trace

    # Assembly is independent of fragment discovery order.
    baseline = fixture_trace.render_trace(trace)
    for permutation in itertools.islice(itertools.permutations(records), 30):
        assert fixture_trace.render_trace(
            assemble(permutation)
        ) == baseline
    default_trace = fixture_trace.assemble_fragments(records)
    assert default_trace["sensitivity"] == "Restricted"
    assert fixture_trace.render_trace(default_trace) != baseline

    # Event coverage is a set on the wire.  Assembly canonicalizes it so
    # producer enumeration order cannot change the trace or comparison.
    branch_event = {"kind": "BranchSuccessor", "field": "successor"}
    reordered = copy.deepcopy(records)
    reordered[2]["record"]["event_coverage"] = [event, branch_event]
    reverse_ordered = copy.deepcopy(reordered)
    reverse_ordered[2]["record"]["event_coverage"].reverse()
    reordered_trace = assemble(reordered)
    assert reordered_trace["decision"]["event_coverage"] == [branch_event, event]
    assert fixture_trace.render_trace(reordered_trace) == fixture_trace.render_trace(
        assemble(reverse_ordered)
    )

    decoded = fixture_trace.checkpoint_model.strict_yaml_load(
        baseline, source="assembled test trace"
    )
    assert decoded == trace

    # With no counterexample fragment, assembly explicitly records None.
    no_counterexample = assemble(
        [row for row in records if row["record"]["tag"] != "ValidatedCounterexample"]
    )
    assert no_counterexample["decision"]["counterexample"] == {"tag": "None"}

    # Expectation, snapshot, comparison, and final-outcome vocabulary is rejected
    # even when hidden inside otherwise free-form extracted facts.
    for forbidden in (
        "expect",
        "expected_result",
        "because",
        "snapshot_path",
        "comparison",
        "matching-details",
        "model_status",
        "test-outcome",
    ):
        poisoned = copy.deepcopy(records[0])
        poisoned["record"]["capture"]["facts"][forbidden] = "Counterexample"
        expect_error(
            lambda poisoned=poisoned: fixture_trace.validate_fragment(poisoned),
            "forbidden expectation or snapshot field",
        )

    invalid_cause = copy.deepcopy(records[3])
    invalid_cause["record"]["counterexample"]["cause"] = "has spaces"
    expect_error(
        lambda: fixture_trace.validate_fragment(invalid_cause), "invalid value"
    )
    invalid_reason = copy.deepcopy(records[4])
    invalid_reason["record"]["blocker"]["reason"] = "has spaces"
    expect_error(
        lambda: fixture_trace.validate_fragment(invalid_reason), "invalid value"
    )

    extra = copy.deepcopy(records[0])
    extra["snapshot"] = "snapshot.yaml"
    expect_error(lambda: fixture_trace.validate_fragment(extra), "forbidden")
    invalid_fact = copy.deepcopy(records[0])
    invalid_fact["record"]["capture"]["facts"]["ratio"] = 0.5
    expect_error(
        lambda: fixture_trace.validate_fragment(invalid_fact), "floating-point"
    )
    boundary_fact_key = copy.deepcopy(records[0])
    boundary_fact_key["record"]["capture"]["facts"] = {"k" * 256: "value"}
    fixture_trace.validate_fragment(boundary_fact_key)
    oversized_fact_key = copy.deepcopy(records[0])
    oversized_fact_key["record"]["capture"]["facts"] = {"k" * 257: "value"}
    expect_error(
        lambda: fixture_trace.validate_fragment(oversized_fact_key),
        "exceeds maximum length 256",
    )

    duplicate_capture = records + [copy.deepcopy(records[0])]
    expect_error(
        lambda: assemble(duplicate_capture),
        "duplicate PipelineCapture",
    )
    duplicate_checks = records + [copy.deepcopy(records[2])]
    expect_error(
        lambda: assemble(duplicate_checks),
        "duplicate RequiredChecks",
    )
    duplicate_final = records + [copy.deepcopy(records[-1])]
    expect_error(
        lambda: assemble(duplicate_final),
        "duplicate FinalAxes",
    )

    wrong_case = copy.deepcopy(records)
    wrong_case[1]["case"] = "contract/other"
    expect_error(
        lambda: assemble(wrong_case),
        "session/case/entry",
    )
    expect_error(
        lambda: assemble(
            [row for row in records if row["record"]["tag"] != "RequiredChecks"]
        ),
        "RequiredChecks",
    )
    expect_error(
        lambda: assemble(
            [row for row in records if row["record"]["tag"] != "FinalAxes"]
        ),
        "FinalAxes",
    )

    # The inherited strict loader rejects YAML features outside the closed JSON
    # data model before record validation sees them.
    base_yaml = yaml.safe_dump(records[0], sort_keys=False).encode()
    duplicate_yaml = base_yaml + b"format: SPS-Harness-Trace-Fragment\n"
    expect_error(
        lambda: fixture_trace.parse_fragment(duplicate_yaml), "duplicate key"
    )
    alias_yaml = b"format: &f SPS-Harness-Trace-Fragment\ncopy: *f\n"
    expect_error(lambda: fixture_trace.parse_fragment(alias_yaml), "aliases")
    tagged_yaml = base_yaml.replace(
        b"operation.count: 2", b"operation.count: !!int 2"
    )
    expect_error(lambda: fixture_trace.parse_fragment(tagged_yaml), "explicit tags")
    null_yaml = base_yaml.replace(b"facts:\n", b"facts:\n      null-value: null\n")
    expect_error(lambda: fixture_trace.parse_fragment(null_yaml), "null")
    for null_scalar in ("~", "Null", "NULL", ""):
        expect_error(
            lambda null_scalar=null_scalar: fixture_trace.parse_fragment(
                base_yaml.replace(
                    b"facts:\n",
                    f"facts:\n      null-value: {null_scalar}\n".encode(),
                )
            ),
            "null",
        )
    expect_error(
        lambda: fixture_trace.parse_fragment(b"\xef\xbb\xbf" + base_yaml), "BOM"
    )

    def yaml_with_fact(key: str, scalar: str) -> bytes:
        insertion = f"facts:\n      {key}: {scalar}\n".encode()
        return base_yaml.replace(b"facts:\n", insertion, 1)

    # The Python producer and C consumer share a deliberately smaller scalar
    # language than YAML. Only lowercase plain true/false are booleans, and
    # integers use canonical signed int64 decimal spelling.
    scalar_cases = {
        "bool-true": ("true", True),
        "bool-false": ("false", False),
        "int-zero": ("0", 0),
        "int-min": ("-9223372036854775808", -(1 << 63)),
        "int-max": ("9223372036854775807", (1 << 63) - 1),
        "word-true": ("True", "True"),
        "word-yes": ("yes", "yes"),
        "alphanumeric": ("123abc", "123abc"),
        "quoted-number": ('"01"', "01"),
        "quoted-null": ('"null"', "null"),
    }
    for key, (scalar, expected) in scalar_cases.items():
        parsed = fixture_trace.parse_fragment(yaml_with_fact(key, scalar))
        actual = parsed["record"]["capture"]["facts"][key]
        assert actual == expected and type(actual) is type(expected), (
            key,
            expected,
            actual,
        )

    rejected_numeric_scalars = (
        "-0",
        "+1",
        "01",
        "-01",
        "1_000",
        "0x10",
        "0o10",
        "0b10",
        "1:20",
        "0.5",
        ".5",
        "1e3",
        "1.",
        ".inf",
        "-.NaN",
    )
    for index, scalar in enumerate(rejected_numeric_scalars):
        expect_error(
            lambda index=index, scalar=scalar: fixture_trace.parse_fragment(
                yaml_with_fact(f"noncanonical-{index}", scalar)
            ),
            "numeric scalars are forbidden",
        )
    for scalar in ("9223372036854775808", "-9223372036854775809"):
        expect_error(
            lambda scalar=scalar: fixture_trace.parse_fragment(
                yaml_with_fact("overflow", scalar)
            ),
            "outside signed int64 range",
        )

    in_memory_overflow = copy.deepcopy(records[0])
    in_memory_overflow["record"]["capture"]["facts"]["overflow"] = 1 << 63
    expect_error(
        lambda: fixture_trace.validate_fragment(in_memory_overflow),
        "outside signed int64 range",
    )

    # Construction is bounded exactly like the C reader: root depth is zero,
    # depth 64 is admitted, and the next value is rejected before PyYAML can
    # recurse. Node and final wire-size caps apply to in-memory producers too.
    admitted_nesting = "[" * 60 + "0" + "]" * 60
    fixture_trace.parse_fragment(yaml_with_fact("nested", admitted_nesting))
    for nesting in (61, 500):
        nested_scalar = "[" * nesting + "0" + "]" * nesting
        expect_error(
            lambda nested_scalar=nested_scalar: fixture_trace.parse_fragment(
                yaml_with_fact("nested", nested_scalar)
            ),
            "YAML nesting limit exceeded",
        )

    node_heavy = copy.deepcopy(records[0])
    node_heavy["record"]["capture"]["facts"]["many"] = [
        0
    ] * fixture_trace._MAX_YAML_NODES
    expect_error(
        lambda: fixture_trace.validate_fragment(node_heavy),
        "YAML node limit exceeded",
    )

    oversized_trace = copy.deepcopy(trace)
    oversized_trace["captures"]["modeled-shape"]["facts"]["large"] = (
        "x" * fixture_trace._MAX_FRAGMENT_BYTES
    )
    expect_error(
        lambda: fixture_trace.render_trace(oversized_trace),
        "input exceeds 4 MiB limit",
    )

    # Aggregate limits apply before assemble_fragments returns, not only when a
    # CLI caller happens to render the returned mapping.
    node_capture_a = copy.deepcopy(records[0])
    node_capture_a["record"]["pipeline"] = "large-a"
    node_capture_a["record"]["capture"]["facts"] = {"many": [0] * 49_990}
    node_capture_b = copy.deepcopy(records[0])
    node_capture_b["record"]["pipeline"] = "large-b"
    node_capture_b["record"]["capture"]["facts"] = {"many": [0] * 49_990}
    expect_error(
        lambda: fixture_trace.assemble_fragments(
            [node_capture_a, node_capture_b, records[2], records[-1]],
            sensitivity="SyntheticTestData",
        ),
        "YAML node limit exceeded",
    )

    byte_capture_a = copy.deepcopy(records[0])
    byte_capture_a["record"]["pipeline"] = "bytes-a"
    byte_capture_a["record"]["capture"]["facts"] = {
        "large": "x" * (fixture_trace._MAX_FRAGMENT_BYTES // 2 + 1024)
    }
    byte_capture_b = copy.deepcopy(records[0])
    byte_capture_b["record"]["pipeline"] = "bytes-b"
    byte_capture_b["record"]["capture"]["facts"] = {
        "large": "x" * (fixture_trace._MAX_FRAGMENT_BYTES // 2 + 1024)
    }
    expect_error(
        lambda: fixture_trace.assemble_fragments(
            [byte_capture_a, byte_capture_b, records[2], records[-1]],
            sensitivity="SyntheticTestData",
        ),
        "input exceeds 4 MiB limit",
    )

    with tempfile.TemporaryDirectory() as aggregate_directory:
        aggregate_root = Path(aggregate_directory)
        raw_a = yaml.safe_dump(records[0], sort_keys=False).encode("utf-8")
        raw_b = yaml.safe_dump(records[1], sort_keys=False).encode("utf-8")
        pad = b"#" + b"x" * (fixture_trace._MAX_FRAGMENT_BYTES // 2)
        path_a = aggregate_root / "a.yaml"
        path_b = aggregate_root / "b.yaml"
        path_a.write_bytes(raw_a + pad)
        path_b.write_bytes(raw_b + pad)
        expect_error(
            lambda: fixture_trace.assemble_fragment_files(
                [path_a, path_b], sensitivity="SyntheticTestData"
            ),
            "aggregate fragment input exceeds 4 MiB limit",
        )

    whitespace_failure = copy.deepcopy(records[1])
    whitespace_failure["record"]["capture"]["error"] = " "
    whitespace_failure["record"]["capture"]["blocked_by"] = [" "]
    fixture_trace.validate_fragment(whitespace_failure)

    nul_yaml = yaml_with_fact("nul-value", '"\\0"')
    expect_error(lambda: fixture_trace.parse_fragment(nul_yaml), "embedded NUL")
    nul_value = copy.deepcopy(records[0])
    nul_value["record"]["capture"]["facts"]["nul-value"] = "a\0b"
    expect_error(lambda: fixture_trace.validate_fragment(nul_value), "embedded NUL")
    nul_key = copy.deepcopy(records[0])
    nul_key["record"]["capture"]["facts"]["nul\0key"] = "value"
    expect_error(lambda: fixture_trace.validate_fragment(nul_key), "embedded NUL")

    surrogate_yaml = yaml_with_fact("surrogate", '"\\uD800"')
    expect_error(
        lambda: fixture_trace.parse_fragment(surrogate_yaml), "surrogate code points"
    )
    out_of_range_yaml = yaml_with_fact("out-of-range", '"\\U00110000"')
    expect_error(
        lambda: fixture_trace.parse_fragment(out_of_range_yaml),
        "invalid strict YAML",
    )
    surrogate_value = copy.deepcopy(records[0])
    surrogate_value["record"]["capture"]["facts"]["surrogate"] = "\ud800"
    expect_error(
        lambda: fixture_trace.validate_fragment(surrogate_value),
        "surrogate code points",
    )
    surrogate_key = copy.deepcopy(records[0])
    surrogate_key["record"]["capture"]["facts"]["key-\ud800"] = "value"
    expect_error(
        lambda: fixture_trace.validate_fragment(surrogate_key),
        "surrogate code points",
    )

    # The CLI exposes fragments and sensitivity only. Argparse must reject a
    # snapshot option rather than silently treating it as evidence.
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        paths = []
        for index, row in enumerate(records):
            path = directory / f"{index}.yaml"
            path.write_text(yaml.safe_dump(row, sort_keys=False))
            paths.append(path)
        completed = subprocess.run(
            [
                sys.executable,
                str(tools / "fixture_trace.py"),
                "assemble",
                "--sensitivity",
                "SyntheticTestData",
                *map(str, paths),
            ],
            check=True,
            stdout=subprocess.PIPE,
        )
        assert fixture_trace.checkpoint_model.strict_yaml_load(
            completed.stdout, source="CLI trace"
        ) == trace
        rejected = subprocess.run(
            [
                sys.executable,
                str(tools / "fixture_trace.py"),
                "assemble",
                "--snapshot",
                "snapshot.yaml",
                *map(str, paths),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert rejected.returncode != 0
        assert b"unrecognized arguments" in rejected.stderr

        restricted_stdout = subprocess.run(
            [
                sys.executable,
                str(tools / "fixture_trace.py"),
                "assemble",
                *map(str, paths),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert restricted_stdout.returncode == 2
        assert restricted_stdout.stdout == b""
        assert b"explicit output file" in restricted_stdout.stderr

        restricted_path = directory / "restricted-trace.yaml"
        restricted_created = subprocess.run(
            [
                sys.executable,
                str(tools / "fixture_trace.py"),
                "assemble",
                "--sensitivity",
                "Restricted",
                "-o",
                str(restricted_path),
                *map(str, paths),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert restricted_created.returncode == 0, restricted_created.stderr
        assert restricted_created.stdout == b""
        assert stat.S_IMODE(restricted_path.stat().st_mode) == 0o600
        restricted_trace = fixture_trace._strict_yaml_load(
            restricted_path.read_bytes(), source="restricted CLI trace"
        )
        assert restricted_trace["sensitivity"] == "Restricted"

        original = restricted_path.read_bytes()
        restricted_existing = subprocess.run(
            [
                sys.executable,
                str(tools / "fixture_trace.py"),
                "assemble",
                "--sensitivity",
                "Restricted",
                "-o",
                str(restricted_path),
                *map(str, paths),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert restricted_existing.returncode == 2
        assert b"refusing to overwrite" in restricted_existing.stderr
        assert restricted_path.read_bytes() == original

        symlink_destination = directory / "symlink-destination.yaml"
        symlink_destination.write_bytes(b"must remain unchanged")
        symlink_output = directory / "restricted-symlink.yaml"
        os.symlink(symlink_destination, symlink_output)
        restricted_symlink = subprocess.run(
            [
                sys.executable,
                str(tools / "fixture_trace.py"),
                "assemble",
                "--sensitivity",
                "Restricted",
                "-o",
                str(symlink_output),
                *map(str, paths),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert restricted_symlink.returncode == 2
        assert b"refusing to overwrite" in restricted_symlink.stderr
        assert symlink_output.is_symlink()
        assert symlink_destination.read_bytes() == b"must remain unchanged"

    print("expectation-blind fixture trace assembly passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
