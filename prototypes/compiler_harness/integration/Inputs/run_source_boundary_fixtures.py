#!/usr/bin/env python3
"""Run every case-local source-boundary checkpoint owned by one lit test."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TEST = "integration/source-boundary-fixtures.test"
PIPELINE = "source-boundary"
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx"}


def _case_inputs(
    snapshot: object, checkpoint_model: object
) -> tuple[Path, Path, Path, tuple[Path, ...]]:
    snapshot_path = snapshot.path
    case = snapshot_path.parent
    abi = case / "abi.sps.yaml"
    policy = case / "policy.sps.yaml"
    try:
        abi_value = checkpoint_model.strict_yaml_load(
            abi.read_bytes(), source=str(abi)
        )
    except OSError as error:
        raise SystemExit(f"{snapshot_path}: cannot read {abi.name}: {error}") from error
    source_name = abi_value.get("source")
    if (
        not isinstance(source_name, str)
        or Path(source_name).name != source_name
        or Path(source_name).suffix not in SOURCE_SUFFIXES
    ):
        raise SystemExit(
            f"{abi}: source must name a sibling C/C++ translation unit"
        )
    primary = case / source_name
    for label, path in (("ABI", abi), ("policy", policy), ("primary source", primary)):
        if not path.is_file():
            raise SystemExit(f"{snapshot_path}: missing {label}: {path}")
    support = tuple(
        sorted(
            path
            for path in case.iterdir()
            if path.is_file()
            and path.suffix in SOURCE_SUFFIXES
            and path != primary
        )
    )
    return primary, policy, abi, support


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-pipeline", required=True, choices=[PIPELINE])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--outputs", required=True, type=Path)
    parser.add_argument("--clang", required=True, type=Path)
    parser.add_argument("--llvm-config", required=True, type=Path)
    arguments = parser.parse_args()

    root = arguments.root.resolve()
    sys.path.insert(0, str(root / "tools"))
    import checkpoint_model

    runner = root / "tools" / "checkpoint_runner.py"
    boundary = root / "tools" / "sps_boundary.py"
    arguments.outputs.mkdir(parents=True, exist_ok=True)
    owned = 0
    inventory = checkpoint_model.build_inventory(root)
    for snapshot in inventory.snapshots:
        pipeline = snapshot.pipelines.get(PIPELINE)
        if pipeline is None or pipeline.test != TEST:
            continue
        snapshot_path = snapshot.path
        primary, policy, abi, support = _case_inputs(snapshot, checkpoint_model)
        endpoint = arguments.outputs / f"{snapshot.case.replace('/', '--')}.json"
        command = [
            sys.executable,
            str(runner),
            "run",
            "--root",
            str(root),
            "--snapshot",
            str(snapshot_path.relative_to(root)),
            "--pipeline",
            PIPELINE,
            "--endpoint",
            str(endpoint),
            "--records",
            str(arguments.records),
            "--",
            sys.executable,
            str(boundary),
            "--clang",
            str(arguments.clang),
            "--llvm-config",
            str(arguments.llvm_config),
            "--source",
            str(primary),
        ]
        for support_source in support:
            command.extend(["--support-source", str(support_source)])
        command.extend([
            "--policy",
            str(policy),
            "--abi",
            str(abi),
            "--report",
            str(endpoint),
        ])
        subprocess.run(command, check=True)
        owned += 1
    if owned == 0:
        raise SystemExit(f"no {PIPELINE!r} checkpoints are owned by {TEST}")
    print(f"ran {owned} case-local source-boundary checkpoints")


if __name__ == "__main__":
    main()
