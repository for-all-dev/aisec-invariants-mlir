#!/usr/bin/env python3
"""Pin the exact resolved boundary for the audience-mismatch regression."""

from __future__ import annotations

import json
import sys
from pathlib import Path


EXPECTED_COALITIONS = [
    {
        "members": ["alice", "bob"],
        "visible-components": [],
        "visible-hosts": ["alice-endpoint", "bob-endpoint"],
        "visible-outputs": [],
        "authorized-releases": ["masked-class"],
    },
    {
        "members": ["alice"],
        "visible-components": [],
        "visible-hosts": ["alice-endpoint"],
        "visible-outputs": [],
        "authorized-releases": ["masked-class"],
    },
    {
        "members": ["bob"],
        "visible-components": [],
        "visible-hosts": ["bob-endpoint"],
        "visible-outputs": [],
        "authorized-releases": [],
    },
    {
        "members": [],
        "visible-components": [],
        "visible-hosts": [],
        "visible-outputs": [],
        "authorized-releases": [],
    },
]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_audience_boundary.py RESOLVED.json")
    path = Path(sys.argv[1])
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read resolved audience boundary: {error}") from error
    if value.get("principals") != ["alice", "bob"]:
        raise SystemExit(f"audience principals mismatch: {value.get('principals')!r}")
    if value.get("coalitions") != EXPECTED_COALITIONS:
        raise SystemExit(
            "audience coalition rows mismatch:\n"
            f"expected={EXPECTED_COALITIONS!r}\nactual={value.get('coalitions')!r}"
        )
    releases = value.get("releases")
    if not isinstance(releases, list) or len(releases) != 1:
        raise SystemExit(f"audience release rows mismatch: {releases!r}")
    release = releases[0]
    expected_release = {
        "id": "masked-class",
        "helper": "masked-class",
        "helper-symbol": "sps_release_masked_class_candidate",
        "call-ordinal": 0,
    }
    for key, expected in expected_release.items():
        if release.get(key) != expected:
            raise SystemExit(
                f"audience release {key} mismatch: expected {expected!r}, got {release.get(key)!r}"
            )
    contracts = value.get("contracts")
    expected_contracts = [
        {
            "id": "transfer-alice",
            "callee": "sps_transfer_audience_alice",
            "call-ordinal": 0,
            "source-host": "compute",
            "destination-host": "alice-endpoint",
            "signature": "void (i32)",
            "claim-boundary": "NonClaimableAuthoringLocator",
        },
        {
            "id": "transfer-bob",
            "callee": "sps_transfer_audience_bob",
            "call-ordinal": 0,
            "source-host": "compute",
            "destination-host": "bob-endpoint",
            "signature": "void (i32)",
            "claim-boundary": "NonClaimableAuthoringLocator",
        },
    ]
    if not isinstance(contracts, list) or len(contracts) != len(expected_contracts):
        raise SystemExit(f"audience contract rows mismatch: {contracts!r}")
    for actual, expected in zip(contracts, expected_contracts, strict=True):
        for key, expected_value in expected.items():
            if actual.get(key) != expected_value:
                raise SystemExit(
                    f"audience contract {key} mismatch: expected {expected_value!r}, "
                    f"got {actual.get(key)!r}"
                )
    print("audience source boundary matches all four coalition rows")


if __name__ == "__main__":
    main()
