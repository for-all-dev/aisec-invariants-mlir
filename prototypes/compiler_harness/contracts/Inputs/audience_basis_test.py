#!/usr/bin/env python3
"""Exact SPS audience-basis derivation and refusal checks."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable


def expect_error(action: Callable[[], object], needle: str) -> None:
    try:
        action()
    except ValueError as error:
        if needle not in str(error):
            raise AssertionError(f"missing diagnostic {needle!r}: {error}") from error
    else:
        raise AssertionError(f"operation unexpectedly accepted; wanted {needle!r}")


def policy_with_audience(audience: object) -> dict[str, Any]:
    return {
        "entry": "audience-basis",
        "observation-model": "constant-time",
        "principals": ["alice", "bob", "charlie"],
        "adversaries": {"maximal": [["alice", "bob", "charlie"]]},
        "hosts": {"compute": {"visibility": "secret"}},
        "components": {
            "secret": {
                "lifecycle": "entry-input",
                "type": "bv32",
                "visibility": "secret",
            }
        },
        "outputs": {},
        "releases": {
            "value": {
                "locator": {"helper": "value", "call-ordinal": 0},
                "audience": audience,
                "type": {"kind": "bv", "width": 32, "byte-order": "little"},
                "expression": {"component": "secret"},
                "guard": True,
                "payload-footprint": [0, 1, 2, 3],
                "multiplicity": 1,
            }
        },
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: audience_basis_test.py HARNESS")
    harness = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(harness / "tools"))

    from source_boundary import schema as authoring_schema
    from source_boundary.resolver import (
        BoundaryError,
        _coalitions,
        _is_visible,
        _visibility,
    )

    principals = {"alice", "bob", "charlie"}
    policy = policy_with_audience("secret")
    coalitions = _coalitions(policy)
    ordered = [sorted(coalition) for coalition in coalitions]
    assert ordered == [
        ["alice", "bob", "charlie"],
        ["alice", "bob"],
        ["alice", "charlie"],
        ["alice"],
        ["bob", "charlie"],
        ["bob"],
        ["charlie"],
        [],
    ]

    bases = {
        "world": _visibility(
            {"world": True, "members": [], "joint": []}, principals, "world"
        ),
        "member-alice": _visibility(
            {"world": False, "members": ["alice"], "joint": []},
            principals,
            "member-alice",
        ),
        "joint-alice-bob": _visibility(
            {"world": False, "members": [], "joint": [["alice", "bob"]]},
            principals,
            "joint-alice-bob",
        ),
        "none": _visibility(
            {"world": False, "members": [], "joint": []}, principals, "none"
        ),
    }
    actual = {
        tuple(sorted(coalition)): {
            name: _is_visible(basis, coalition) for name, basis in bases.items()
        }
        for coalition in coalitions
    }
    expected = {
        (): {"world": True, "member-alice": False, "joint-alice-bob": False, "none": False},
        ("alice",): {"world": True, "member-alice": True, "joint-alice-bob": False, "none": False},
        ("bob",): {"world": True, "member-alice": False, "joint-alice-bob": False, "none": False},
        ("charlie",): {"world": True, "member-alice": False, "joint-alice-bob": False, "none": False},
        ("alice", "bob"): {"world": True, "member-alice": True, "joint-alice-bob": True, "none": False},
        ("alice", "charlie"): {"world": True, "member-alice": True, "joint-alice-bob": False, "none": False},
        ("bob", "charlie"): {"world": True, "member-alice": False, "joint-alice-bob": False, "none": False},
        ("alice", "bob", "charlie"): {"world": True, "member-alice": True, "joint-alice-bob": True, "none": False},
    }
    assert actual == expected
    print("derived all eight coalitions and exact world/member/joint/none visibility")

    member_or = _visibility(
        {"world": False, "members": ["alice", "bob"], "joint": []},
        principals,
        "member-or",
    )
    joint_and = bases["joint-alice-bob"]
    singleton_alice = frozenset({"alice"})
    singleton_bob = frozenset({"bob"})
    pair = frozenset({"alice", "bob"})
    assert _is_visible(member_or, singleton_alice)
    assert _is_visible(member_or, singleton_bob)
    assert not _is_visible(joint_and, singleton_alice)
    assert not _is_visible(joint_and, singleton_bob)
    assert _is_visible(joint_and, pair)
    print("distinguished member OR from joint AND semantics")

    assert _visibility("public", principals, "public") == bases["world"]
    assert _visibility("secret", principals, "secret") == bases["none"]
    print("accepted public/secret shorthand normalization")

    schema = authoring_schema.load_schema(
        harness / "source-annotations" / "schemas" / "policy.schema.json"
    )

    duplicate_member = policy_with_audience(
        {"world": False, "members": ["alice", "alice"], "joint": []}
    )
    expect_error(
        lambda: authoring_schema.validate(
            duplicate_member, schema, source="duplicate-member"
        ),
        "expected exactly one schema alternative",
    )

    singleton_joint = policy_with_audience(
        {"world": False, "members": [], "joint": [["alice"]]}
    )
    expect_error(
        lambda: authoring_schema.validate(singleton_joint, schema, source="singleton-joint"),
        "expected exactly one schema alternative",
    )

    repeated_joint_member = policy_with_audience(
        {"world": False, "members": [], "joint": [["alice", "alice"]]}
    )
    expect_error(
        lambda: authoring_schema.validate(
            repeated_joint_member, schema, source="repeated-joint-member"
        ),
        "expected exactly one schema alternative",
    )

    authored_table = policy_with_audience(
        {
            "world": False,
            "members": ["alice"],
            "joint": [],
            "coalitions": [{"members": ["alice"], "authorized": True}],
        }
    )
    expect_error(
        lambda: authoring_schema.validate(
            authored_table, schema, source="authored-coalition-table"
        ),
        "expected exactly one schema alternative",
    )

    expect_error(
        lambda: _visibility(
            {"world": False, "members": ["mallory"], "joint": []},
            principals,
            "unknown-member",
        ),
        "unknown principals",
    )
    expect_error(
        lambda: _visibility(
            {
                "world": False,
                "members": [],
                "joint": [["alice", "mallory"]],
            },
            principals,
            "unknown-joint-member",
        ),
        "unknown principals",
    )
    expect_error(
        lambda: _visibility(
            {
                "world": False,
                "members": [],
                "joint": [["alice", "bob"], ["bob", "alice"]],
            },
            principals,
            "duplicate-joint",
        ),
        "duplicate semantic joint coalition",
    )
    expect_error(
        lambda: _visibility(
            {
                "world": False,
                "members": [],
                "joint": [
                    ["alice", "bob"],
                    ["alice", "bob", "charlie"],
                ],
            },
            principals,
            "nonminimal-joint",
        ),
        "not inclusion-minimal",
    )
    expect_error(
        lambda: _coalitions(
            {
                "principals": ["alice", "bob", "charlie"],
                "adversaries": {"maximal": [["alice"], ["alice", "bob"]]},
            }
        ),
        "not a maximal-coalition antichain",
    )
    print("rejected malformed and nonminimal audience bases")


if __name__ == "__main__":
    main()
