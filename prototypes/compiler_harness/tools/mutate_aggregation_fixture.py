#!/usr/bin/env python3
"""Build the two-distinct-blocker aggregation fixture used by the negative arms.

No checked-in bundle currently has two AuditAll rows blocked for *different*
reasons, so the spec:4192-4196 collapse was unexercised. This helper mutates an
isolated copy of the `launder-scan` bundle's two derived coalition rows into
that shape so contracts/aggregation-collapse.test can drive it.

It is test scaffolding, not a fixture generator: it only ever writes under the
`--root` copy it is given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BUNDLE = "launder-scan"
CANDIDATE_RELATIVE = Path("fixtures/launder-scan/model-clean-p4-open/candidate")
# Two distinct PublicReasonClassesV2 members, neither of them the collapse class.
BLOCKERS = ("SolverTimeout", "PossibleUB")


def blocked_rows(rows: list[dict]) -> None:
    for row, reason in zip(rows[:2], BLOCKERS, strict=True):
        row["query_outcome"] = {
            "tag": "NotConstructedResultMatcherV2",
            "reason": {"reasonClassId": reason},
        }
        row["replay_expectation"] = {
            "tag": "NotAvailableV2",
            "reason": {"reasonClassId": reason},
        }


def mutate_fixture(root: Path, model_reason: str) -> None:
    directory = root / CANDIDATE_RELATIVE
    report_path = directory / "expected-report.json"
    report = json.loads(report_path.read_text())
    expected = report["expected"]
    blocked_rows(expected["audit_all_expectations"])
    expected["expected_model_status"] = {
        "tag": "Unknown",
        "args": [{"reasonClassId": model_reason}],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    identity_path = directory / "artifact.json"
    identity = json.loads(identity_path.read_text())
    identity["candidate_sidecar_sha256"]["expected-report.json"] = hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    print(
        f"mutated {BUNDLE}: rows blocked by {list(BLOCKERS)}; "
        f"expected_model_status Unknown({model_reason})"
    )


def check_specs(root: Path) -> None:
    """Write the same shape into the local bundle spec and re-run its validator."""
    specs_path = root / CANDIDATE_RELATIVE / "bundle-spec.json"
    specs = json.loads(specs_path.read_text())
    expected = specs["expected_report"]["expected"]
    blocked_rows(expected["audit_all_expectations"])
    expected["expected_model_status"] = {
        "tag": "Unknown",
        "args": [{"reasonClassId": BLOCKERS[0]}],
    }
    specs_path.write_text(json.dumps(specs, indent=2) + "\n")

    sys.path.insert(0, str(root / "tools"))
    import artifact_bundle

    artifact_bundle.load_specs()
    raise SystemExit("bundle-spec validator accepted a narrow Unknown for two blockers")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model-reason")
    parser.add_argument("--check-specs", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.check_specs:
        check_specs(root)
        return
    if not args.model_reason:
        raise SystemExit("--model-reason is required unless --check-specs is given")
    mutate_fixture(root, args.model_reason)


if __name__ == "__main__":
    main()
