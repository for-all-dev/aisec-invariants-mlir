#!/usr/bin/env python3
"""Validate the nonclaimable SPS harness stage-report format.

``SPS-Harness-Stage-Report-v2`` records which fixture checks ran.  It is not a
normative SPS run report and cannot contain a ModelStatus, a receipt, a witness,
or a deployment result.  The sole ``modelStatus`` value is the harness sentinel
``NotComputed``.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


FORMAT_ID = "SPS-Harness-Stage-Report-v2"
FIELDS = {
    "formatId",
    "fixtureTier",
    "stageId",
    "completedChecks",
    "findings",
    "blockers",
    "claimable",
    "modelStatus",
}
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")


class StageReportError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StageReportError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def load_stage_report(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except OSError as error:
        raise StageReportError(f"cannot read report: {error}") from error
    except json.JSONDecodeError as error:
        raise StageReportError(f"invalid JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise StageReportError("stage report must be a JSON object")
    return value


def _identifier_array(value: object, name: str, *, nonempty: bool) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise StageReportError(f"{name} must be an array of identifier strings")
    if nonempty and not value:
        raise StageReportError(f"{name} must contain at least one completed check")
    if any(not IDENTIFIER.fullmatch(item) for item in value):
        raise StageReportError(f"{name} contains a malformed identifier")
    if value != sorted(set(value)):
        raise StageReportError(f"{name} must be sorted and duplicate-free")


def validate_stage_report(value: object, *, source: str = "stage report") -> None:
    """Validate one decoded stage report, including embedded fixture reports."""

    try:
        if not isinstance(value, Mapping):
            raise StageReportError("stage report must be an object")
        actual_fields = set(value)
        if actual_fields != FIELDS:
            missing = sorted(FIELDS - actual_fields)
            extra = sorted(actual_fields - FIELDS)
            raise StageReportError(
                f"wrong fields (missing={missing}, extra={extra})"
            )
        if value["formatId"] != FORMAT_ID:
            raise StageReportError(f"formatId must be {FORMAT_ID}")
        if value["fixtureTier"] != {"tag": "CandidateOnly"}:
            raise StageReportError("fixtureTier must be exactly CandidateOnly")
        if not isinstance(value["stageId"], str) or not IDENTIFIER.fullmatch(
            value["stageId"]
        ):
            raise StageReportError("stageId must be a nonempty identifier")
        _identifier_array(value["completedChecks"], "completedChecks", nonempty=True)
        _identifier_array(value["findings"], "findings", nonempty=False)
        _identifier_array(value["blockers"], "blockers", nonempty=False)
        if value["claimable"] is not False:
            raise StageReportError("claimable must be false")
        if value["modelStatus"] != {"tag": "NotComputed"}:
            raise StageReportError(
                "modelStatus must be the NotComputed harness sentinel; "
                "Proved, Counterexample, and Unknown are forbidden"
            )
    except StageReportError as error:
        raise StageReportError(f"{source}: {error}") from error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.reports:
        try:
            report = load_stage_report(path)
            validate_stage_report(report, source=str(path))
        except StageReportError as error:
            raise SystemExit(error) from error
        print(f"valid nonclaimable stage report: {path}")


if __name__ == "__main__":
    main()
