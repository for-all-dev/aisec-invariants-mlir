#!/usr/bin/env python3
"""Focused positive and mutation contracts for synthetic pair sidecars."""

from __future__ import annotations

import argparse
import copy
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import yaml


Mutation = Callable[[dict[str, Any]], None]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("temporary_root", type=Path)
    parser.add_argument("tools", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.tools.resolve()))

    import checkpoint_model
    import counterexample_pair as pairs

    case = args.temporary_root.resolve() / "fixtures" / "demo" / "bad"
    case.mkdir(parents=True, exist_ok=True)
    snapshot_path = case / "snapshot.yaml"
    snapshot_path.write_text("placeholder: true\n")
    pair_path = case / pairs.FILENAME
    policy_path = case / "policy.sps.yaml"
    abi_path = case / "abi.sps.yaml"

    policy: dict[str, Any] = {
        "entry": "demo",
        "principals": ["authorized", "observer"],
        "adversaries": {"maximal": [["authorized", "observer"]]},
        "components": {
            "public-count": {
                "lifecycle": "entry-input",
                "type": "bv8",
                "visibility": "public",
            },
            "authorized-secret": {
                "lifecycle": "entry-input",
                "type": "bv16",
                "visibility": {
                    "world": False,
                    "members": ["authorized"],
                    "joint": [],
                },
            },
            "secret-buffer": {
                "lifecycle": "entry-input",
                "type": "bytes",
                "visibility": "secret",
            },
        },
    }
    abi: dict[str, Any] = {
        "entry": {"id": "demo"},
        "carriers": {
            "public-count": {"argument": 0, "bit-width": 8},
            "authorized-secret": {"argument": 1, "bit-width": 16},
        },
        "roots": {
            "buffer-root": {
                "argument": 2,
                "extent-bytes": 3,
                "initialization": "initialized",
                "input": "secret-buffer",
            }
        },
    }
    pair: dict[str, Any] = {
        "format_id": pairs.FORMAT_ID,
        "claim_boundary": pairs.CLAIM_BOUNDARY,
        "source_class": pairs.SOURCE_CLASS,
        "entry": "demo",
        "coalition": ["observer"],
        "inputs": {
            "low_equal": {
                "public-count": {"bitvector": {"width": 8, "hex": "2a"}}
            },
            "high_left": {
                "authorized-secret": {
                    "bitvector": {"width": 16, "hex": "0001"}
                },
                "secret-buffer": {"bytes": {"length": 3, "hex": "000102"}},
            },
            "high_right": {
                "authorized-secret": {
                    "bitvector": {"width": 16, "hex": "0002"}
                },
                "secret-buffer": {"bytes": {"length": 3, "hex": "000102"}},
            },
        },
        "expected": {
            "bad_state": "public-output-mismatch",
            "first_difference": {
                "kind": "Output",
                "field": "valueBytes",
                "id": "public-output",
            },
        },
    }

    final = checkpoint_model.FinalExpectation(
        status="Counterexample",
        deployment="Open",
        policy="Complete",
        because="test",
        bad_state="public-output-mismatch",
        events=(
            checkpoint_model.EventExpectation(
                "Output", "valueBytes", "public-output", True
            ),
        ),
    )
    snapshot = checkpoint_model.SnapshotV3(
        path=snapshot_path,
        root=args.temporary_root.resolve(),
        case="demo/bad",
        entry="demo",
        c_evidence=(),
        secret=(),
        public=(),
        allowed=(),
        final=final,
        pipelines={},
        raw={},
    )

    def write(
        pair_value: dict[str, Any] = pair,
        policy_value: dict[str, Any] = policy,
        abi_value: dict[str, Any] = abi,
    ) -> None:
        pair_path.write_text(yaml.safe_dump(pair_value, sort_keys=False))
        policy_path.write_text(yaml.safe_dump(policy_value, sort_keys=False))
        abi_path.write_text(yaml.safe_dump(abi_value, sort_keys=False))

    write()
    loaded = pairs.load_fixture_pair(snapshot)
    assert isinstance(loaded, pairs.CounterexamplePair)
    assert loaded.coalition == ("observer",)
    assert isinstance(loaded.inputs.low_equal["public-count"], pairs.BitVectorValue)
    assert isinstance(loaded.inputs.high_left["secret-buffer"], pairs.BytesValue)
    assert len(loaded.canonical_digest) == 64

    reordered = {key: pair[key] for key in reversed(pair)}
    write(reordered)
    assert pairs.load_fixture_pair(snapshot).canonical_digest == loaded.canonical_digest

    def rejected(
        expected: str,
        *,
        pair_mutation: Mutation | None = None,
        policy_mutation: Mutation | None = None,
        abi_mutation: Mutation | None = None,
    ) -> None:
        candidate_pair = copy.deepcopy(pair)
        candidate_policy = copy.deepcopy(policy)
        candidate_abi = copy.deepcopy(abi)
        if pair_mutation is not None:
            pair_mutation(candidate_pair)
        if policy_mutation is not None:
            policy_mutation(candidate_policy)
        if abi_mutation is not None:
            abi_mutation(candidate_abi)
        write(candidate_pair, candidate_policy, candidate_abi)
        try:
            pairs.load_fixture_pair(snapshot)
        except pairs.CounterexamplePairError as error:
            assert expected in str(error), (expected, str(error))
        else:
            raise AssertionError(f"mutation unexpectedly accepted: {expected}")

    rejected(
        "wrong fields",
        pair_mutation=lambda value: value.update(comment="not in the closed shape"),
    )
    rejected(
        "must be sorted and duplicate-free",
        pair_mutation=lambda value: value.update(
            coalition=["observer", "authorized"]
        ),
    )
    rejected(
        "undeclared principals",
        pair_mutation=lambda value: value.update(coalition=["outsider"]),
    )
    rejected(
        "coalition-visible policy components",
        pair_mutation=lambda value: value["inputs"]["low_equal"].clear(),
    )
    rejected(
        "coalition-hidden policy components",
        pair_mutation=lambda value: value["inputs"]["high_right"].pop(
            "secret-buffer"
        ),
    )

    def malformed_component_key(value: dict[str, Any]) -> None:
        tagged = value["inputs"]["high_left"].pop("authorized-secret")
        value["inputs"]["high_left"]["bad component!"] = tagged

    rejected(
        "malformed stable component identifier",
        pair_mutation=malformed_component_key,
    )

    def integer_component_key(value: dict[str, Any]) -> None:
        tagged = value["inputs"]["high_left"].pop("authorized-secret")
        value["inputs"]["high_left"][7] = tagged

    rejected("mapping keys must be strings", pair_mutation=integer_component_key)

    def equal_high(value: dict[str, Any]) -> None:
        value["inputs"]["high_right"] = copy.deepcopy(value["inputs"]["high_left"])

    rejected("at least one High component must differ", pair_mutation=equal_high)

    def wrong_scalar_width(value: dict[str, Any]) -> None:
        body = value["inputs"]["high_left"]["authorized-secret"]["bitvector"]
        body.update(width=8, hex="01")

    rejected("expected ABI width 16", pair_mutation=wrong_scalar_width)

    def wrong_root_extent(value: dict[str, Any]) -> None:
        body = value["inputs"]["high_left"]["secret-buffer"]["bytes"]
        body.update(length=2, hex="0001")

    rejected("expected ABI extent 3", pair_mutation=wrong_root_extent)
    rejected(
        "lowercase hexadecimal digits",
        pair_mutation=lambda value: value["inputs"]["high_left"][
            "authorized-secret"
        ]["bitvector"].update(hex="00AF"),
    )
    rejected(
        "input byte roots must be initialized",
        abi_mutation=lambda value: value["roots"]["buffer-root"].update(
            initialization="uninitialized"
        ),
    )
    rejected(
        "policy components and ABI scalar/root inputs differ",
        abi_mutation=lambda value: value["carriers"].pop("authorized-secret"),
    )
    rejected(
        "entries must agree",
        pair_mutation=lambda value: value.update(entry="other"),
    )
    rejected(
        "must match snapshot bad_state",
        pair_mutation=lambda value: value["expected"].update(
            bad_state="other-mismatch"
        ),
    )
    rejected(
        "sole first_bad event",
        pair_mutation=lambda value: value["expected"]["first_difference"].update(
            id="other-output"
        ),
    )

    write()
    pair_path.write_text(pair_path.read_text() + "entry: duplicate\n")
    try:
        pairs.load_fixture_pair(snapshot)
    except pairs.CounterexamplePairError as error:
        assert "duplicate key 'entry'" in str(error), str(error)
    else:
        raise AssertionError("duplicate YAML key unexpectedly accepted")

    empty_low_policy = copy.deepcopy(policy)
    empty_low_policy["components"]["public-count"]["visibility"] = "secret"
    empty_low_pair = copy.deepcopy(pair)
    public_value = empty_low_pair["inputs"]["low_equal"].pop("public-count")
    empty_low_pair["inputs"]["high_left"]["public-count"] = copy.deepcopy(
        public_value
    )
    empty_low_pair["inputs"]["high_right"]["public-count"] = copy.deepcopy(
        public_value
    )
    write(empty_low_pair, empty_low_policy, abi)
    assert pairs.load_fixture_pair(snapshot).inputs.low_equal == {}

    write()
    pair_path.unlink()
    try:
        pairs.load_fixture_pair(snapshot)
    except pairs.CounterexamplePairError as error:
        assert "requires sibling counterexample-pair.yaml" in str(error), str(error)
    else:
        raise AssertionError("missing Counterexample pair unexpectedly accepted")

    write()
    for status in ("Proved", "Unknown"):
        other = replace(snapshot, final=replace(snapshot.final, status=status))
        try:
            pairs.load_fixture_pair(other)
        except pairs.CounterexamplePairError as error:
            assert "must not have a synthetic counterexample pair" in str(error), str(error)
        else:
            raise AssertionError(f"{status} snapshot pair unexpectedly accepted")

    print("synthetic counterexample-pair contract mutations passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
