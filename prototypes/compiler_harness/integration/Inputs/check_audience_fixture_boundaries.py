#!/usr/bin/env python3
"""Pin the resolver-derived audience rows for the end-to-end fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def row(
    members: list[str],
    hosts: list[str],
    releases: list[str],
) -> dict[str, Any]:
    return {
        "members": members,
        "visible-hosts": hosts,
        "visible-components": [],
        "visible-outputs": [],
        "authorized-releases": releases,
    }


EXPECTED = {
    "audience-joint--authorized": [
        row(["alice", "bob"], ["joint-endpoint"], ["joint-class"]),
        row(["alice"], [], []),
        row(["bob"], [], []),
        row([], [], []),
    ],
    "audience-joint--singleton-visible-bad": [
        row(["alice", "bob"], ["alice-endpoint"], ["joint-class"]),
        row(["alice"], ["alice-endpoint"], []),
        row(["bob"], [], []),
        row([], [], []),
    ],
    "audience-mismatch--authorized-audience": [
        row(
            ["alice", "bob"],
            ["alice-endpoint", "bob-endpoint"],
            ["masked-class"],
        ),
        row(["alice"], ["alice-endpoint"], ["masked-class"]),
        row(["bob"], ["bob-endpoint"], ["masked-class"]),
        row([], [], []),
    ],
    "audience-release--equal-then-leak-bad": [
        row(["observer"], ["observer-endpoint"], ["zero-release"]),
        row([], [], []),
    ],
    "audience-visibility--location-visible-bad": [
        row(["alice", "bob"], ["compute"], ["alice-class"]),
        row(["alice"], [], ["alice-class"]),
        row(["bob"], ["compute"], []),
        row([], [], []),
    ],
    "audience-visibility--unauthorized-concealed": [
        row(["alice", "bob"], [], ["alice-class"]),
        row(["alice"], [], ["alice-class"]),
        row(["bob"], [], []),
        row([], [], []),
    ],
    "audience-world--authorized": [
        row(["observer"], ["world-endpoint"], ["world-class"]),
        row([], ["world-endpoint"], ["world-class"]),
    ],
}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_audience_fixture_boundaries.py OUTPUTS")
    outputs = Path(sys.argv[1])
    for case, expected in EXPECTED.items():
        path = outputs / f"{case}.resolved.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"cannot read {path}: {error}") from error
        actual = value.get("coalitions")
        if actual != expected:
            raise SystemExit(
                f"{case}: audience coalition rows mismatch:\n"
                f"expected={expected!r}\nactual={actual!r}"
            )
    print(f"resolved exact coalition tables for {len(EXPECTED)} audience fixtures")


if __name__ == "__main__":
    main()
