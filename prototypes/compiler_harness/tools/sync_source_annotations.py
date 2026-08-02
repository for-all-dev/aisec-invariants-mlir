#!/usr/bin/env python3
"""Compare or explicitly refresh the harness's SPS source-authoring vendor."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VENDOR_FILES = {
    Path("include/sps/annotations.h"): ROOT / "include" / "sps" / "annotations.h",
    Path("schemas/policy.schema.json"): ROOT
    / "source-annotations"
    / "schemas"
    / "policy.schema.json",
    Path("schemas/abi.schema.json"): ROOT
    / "source-annotations"
    / "schemas"
    / "abi.schema.json",
}


class SyncError(ValueError):
    pass


def _source_files(source: Path) -> dict[Path, Path]:
    source = source.resolve()
    result = {relative: source / relative for relative in VENDOR_FILES}
    missing = [str(path) for path in result.values() if not path.is_file()]
    if missing:
        raise SyncError(f"source package is missing contract files: {missing!r}")
    return result


def compare(source: Path) -> None:
    for relative, source_path in _source_files(source).items():
        vendor_path = VENDOR_FILES[relative]
        if not vendor_path.is_file():
            raise SyncError(f"vendored contract file is missing: {vendor_path}")
        if source_path.read_bytes() != vendor_path.read_bytes():
            raise SyncError(f"source-annotation bytes differ: {relative}")


def update(source: Path) -> None:
    for relative, source_path in _source_files(source).items():
        destination = VENDOR_FILES[relative]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.", dir=destination.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(source_path.read_bytes())
        try:
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            compare(args.source)
            print("SPS source-annotation package matches the harness vendor")
        else:
            update(args.source)
            compare(args.source)
            print("updated SPS source-annotation package vendor")
    except (OSError, SyncError) as error:
        raise SystemExit(f"SPS source-annotation sync failed: {error}") from error


if __name__ == "__main__":
    main()
