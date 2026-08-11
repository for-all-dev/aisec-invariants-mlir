#!/usr/bin/env python3
"""Negative and inventory contracts for minimal Snapshot V3."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any, Callable

import yaml


Mutation = Callable[[dict[str, Any]], None]


def mutate_rejected(
    model: Any,
    root: Path,
    relative: str,
    mutation: Mutation,
    expected: str,
) -> None:
    path = root / relative
    original = path.read_bytes()
    try:
        value = yaml.safe_load(original)
        mutation(value)
        path.write_text(yaml.safe_dump(value, sort_keys=False))
        try:
            model.load_snapshot(path, root)
        except model.CheckpointError as error:
            assert expected in str(error), (expected, str(error))
        else:
            raise AssertionError(f"mutation unexpectedly accepted: {relative}: {expected}")
    finally:
        path.write_bytes(original)


def text_rejected(
    model: Any,
    root: Path,
    relative: str,
    transform: Callable[[str], str],
    expected: str,
) -> None:
    path = root / relative
    original = path.read_bytes()
    try:
        path.write_text(transform(original.decode("utf-8")))
        try:
            model.build_inventory(root)
        except model.CheckpointError as error:
            assert expected in str(error), (expected, str(error))
        else:
            raise AssertionError(f"inventory mutation unexpectedly accepted: {expected}")
    finally:
        path.write_bytes(original)


def first_pipeline(value: dict[str, Any]) -> dict[str, Any]:
    return next(iter(value["expect"]["pipelines"].values()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("tools", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(args.tools.resolve()))
    import checkpoint_model as model

    proved = "fixtures/dynamic-kv-length/fixed/snapshot.yaml"
    counterexample = "fixtures/dynamic-kv-length/bad/snapshot.yaml"
    unknown = "fixtures/release-carrier/lost-bad/snapshot.yaml"
    candidate = "fixtures/abi-alias/disjoint-control/snapshot.yaml"
    timing_proved = "fixtures/kyberslash1-poly-tomsg/fixed/snapshot.yaml"
    relation = "fixtures/precision-control/identical-successor/snapshot.yaml"

    mutate_rejected(
        model,
        root,
        proved,
        lambda value: value.update(format_id="SPS-Harness-Fixture-Snapshot-v2"),
        "format_id must be 'SPS-Harness-Fixture-Snapshot-v3'",
    )
    mutate_rejected(
        model,
        root,
        proved,
        lambda value: value["expect"].pop("final"),
        "wrong fields",
    )
    mutate_rejected(
        model,
        root,
        proved,
        lambda value: value["expect"]["final"].pop("events"),
        "Proved requires event coverage",
    )
    mutate_rejected(
        model,
        root,
        counterexample,
        lambda value: value["expect"]["final"].pop("events"),
        "Counterexample requires event coverage",
    )

    def proved_first_bad(value: dict[str, Any]) -> None:
        value["expect"]["final"]["events"][0]["first_bad"] = True

    mutate_rejected(model, root, proved, proved_first_bad, "legal only for Counterexample")

    def no_first_bad(value: dict[str, Any]) -> None:
        value["expect"]["final"]["events"][0].pop("first_bad")

    mutate_rejected(
        model,
        root,
        counterexample,
        no_first_bad,
        "Counterexample requires exactly one first_bad event",
    )

    def two_first_bad(value: dict[str, Any]) -> None:
        event = copy.deepcopy(value["expect"]["final"]["events"][0])
        event["first_bad"] = True
        value["expect"]["final"]["events"].append(event)

    mutate_rejected(
        model,
        root,
        counterexample,
        two_first_bad,
        "Counterexample requires exactly one first_bad event",
    )

    def first_bad_missing_logical_id(value: dict[str, Any]) -> None:
        value["expect"]["final"]["events"][0].pop("id")

    mutate_rejected(
        model,
        root,
        counterexample,
        first_bad_missing_logical_id,
        "first_bad Output event requires a logical ID",
    )

    def raw_payload(value: dict[str, Any]) -> None:
        value["expect"]["final"]["events"][0]["valueBytes"] = "secret"

    mutate_rejected(model, root, counterexample, raw_payload, "wrong fields")
    mutate_rejected(
        model,
        root,
        counterexample,
        lambda value: value["expect"]["final"]["events"][0].update(kind="Trace"),
        "unknown Theta_ct event kind",
    )
    mutate_rejected(
        model,
        root,
        counterexample,
        lambda value: value["expect"]["final"]["events"][0].update(field="address"),
        "is not a field of",
    )
    mutate_rejected(
        model,
        root,
        counterexample,
        lambda value: value["expect"]["final"].update(trace=[]),
        "wrong fields",
    )

    def old_pipeline_fields(value: dict[str, Any]) -> None:
        first_pipeline(value).update(
            execution="active",
            test="fixtures/example.mlir",
            requires=["feature"],
            inputs=[],
            endpoint={"tag": "StructuralEndpointV1"},
        )

    mutate_rejected(model, root, proved, old_pipeline_fields, "wrong fields")

    def old_matcher(value: dict[str, Any]) -> None:
        pipeline = first_pipeline(value)
        fact = next(iter(pipeline["properties"]))
        matcher = pipeline["properties"][fact]
        if "contains" in matcher:
            matcher["contains_all"] = matcher.pop("contains")
        elif "ordered" in matcher:
            matcher["ordered_subsequence"] = matcher.pop("ordered")
        else:
            matcher["regex"] = ".*"

    mutate_rejected(model, root, proved, old_matcher, "matcher must use only")
    mutate_rejected(
        model,
        root,
        proved,
        lambda value: first_pipeline(value).update(kind="terminal-report"),
        "expected one of",
    )

    mutate_rejected(
        model,
        root,
        relation,
        lambda value: value["expect"]["pipelines"]["relation-reference"].update(
            profile="SPS-Reference-Relation-unknown"
        ),
        "unknown relation-reference profile",
    )

    def unknown_relation_fact(value: dict[str, Any]) -> None:
        value["expect"]["pipelines"]["relation-reference"]["properties"][
            "query.normative-model-status"
        ] = {"equals": "Proved"}

    mutate_rejected(
        model,
        root,
        relation,
        unknown_relation_fact,
        "unknown relation-reference facts",
    )

    def bad_event_id(value: dict[str, Any]) -> None:
        value["expect"]["final"]["events"][0]["id"] = "timing-site"

    mutate_rejected(model, root, timing_proved, bad_event_id, "logical IDs apply only")

    def cex_missing_bad_state(value: dict[str, Any]) -> None:
        value["expect"]["final"]["model"].pop("bad_state")

    mutate_rejected(model, root, counterexample, cex_missing_bad_state, "wrong fields")
    mutate_rejected(
        model,
        root,
        unknown,
        lambda value: value["expect"]["final"]["model"].pop("reason"),
        "wrong fields",
    )

    def candidate_disagreement(value: dict[str, Any]) -> None:
        value["expect"]["final"]["model"] = {
            "status": "Unknown",
            "reason": "OpenModelObligations",
        }
        value["expect"]["final"].pop("events")

    mutate_rejected(
        model,
        root,
        candidate,
        candidate_disagreement,
        "candidate final projection disagrees",
    )

    def digest_escape(value: dict[str, Any]) -> None:
        value["expect"]["pipelines"]["candidate-bitcode"]["digest"]["manifest"] = (
            "../artifact.json"
        )

    mutate_rejected(model, root, candidate, digest_escape, "snapshot-relative")

    snapshots = model.load_snapshots(root)
    inventory = model.build_inventory(root)
    assert len(snapshots) == 74
    assert sum(len(item.pipelines) for item in snapshots) == 203
    assert model.outcome_totals(snapshots) == {
        "Counterexample": 30,
        "Proved": 32,
        "Unknown": 12,
    }
    assert sum(item.final.reference is not None for item in snapshots) == 13
    assert sum(
        event.first_bad
        for snapshot in snapshots
        for event in snapshot.final.events
    ) == 30
    assert all(item.final.deployment == "Open" for item in snapshots)
    assert all(item.final.policy == "Complete" for item in snapshots)
    assert len(inventory.run_bindings) == 203
    assert len(inventory.finalizers) == 87

    source = next(item for item in inventory.snapshots if item.case == "kyberslash1-poly-tomsg/bad")
    assert source.pipelines["scanner-diagnostic"].requires == ("sps-scan-unary",)

    direct_test = "fixtures/dynamic-kv-length/fixed/dynamic_kv_length.fixed.mlir"

    def remove_modeled_run(text: str) -> str:
        return "\n".join(
            line
            for line in text.splitlines()
            if not ("checkpoint-runner run" in line and "--pipeline modeled-shape" in line)
        ) + "\n"

    text_rejected(model, root, direct_test, remove_modeled_run, "missing RUN binding")

    def duplicate_modeled_run(text: str) -> str:
        line = next(
            row
            for row in text.splitlines()
            if "checkpoint-runner run" in row and "--pipeline modeled-shape" in row
        )
        return text + line + "\n"

    text_rejected(model, root, direct_test, duplicate_modeled_run, "duplicate RUN binding")
    text_rejected(
        model,
        root,
        direct_test,
        lambda text: "\n".join(
            line for line in text.splitlines() if "checkpoint-runner finalize" not in line
        )
        + "\n",
        "expected exactly one checkpoint finalizer, got 0",
    )

    bytes_test = "fixtures/abi-alias/disjoint-control/abi_alias_disjoint.control.mlir"
    text_rejected(
        model,
        root,
        bytes_test,
        lambda text: text.replace(
            " --endpoint fixtures/abi-alias/disjoint-control/candidate/artifact.bc", ""
        ),
        "check-existing requires --endpoint",
    )

    print("minimal Snapshot V3 model and inventory contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
