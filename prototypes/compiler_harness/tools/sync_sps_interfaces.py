#!/usr/bin/env python3
"""Atomically update or compare the harness's vendored SPS interfaces."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

import sps_interfaces


def source_paths(root: Path) -> tuple[Path, Path]:
    root = root.resolve()
    if (root / "dist").is_dir():
        return root / "dist", root / "interface-manifest.json"
    return root, root.parent / "interface-manifest.json"


def lock_value(manifest: dict[str, object], registry: sps_interfaces.Registry) -> dict[str, object]:
    return {
        "formatId": "SPS-Harness-Interface-Lock-v2",
        "schemaSetId": manifest["schemaSetId"],
        "specRevision": manifest["specRevision"],
        "sourceRevision": manifest["sourceRevision"],
        "bundleSha256": manifest["bundle"]["sha256"],
        "registrySha256": sps_interfaces.sha256(sps_interfaces.canonical_bytes(registry.value)),
    }


def compare(source_dist: Path, source_manifest: Path) -> None:
    if source_manifest.read_bytes() != sps_interfaces.VENDOR_MANIFEST.read_bytes():
        raise sps_interfaces.InterfaceError("upstream and vendored manifests differ")
    source_files = {
        path.relative_to(source_dist) for path in source_dist.rglob("*") if path.is_file()
    }
    vendor_files = {
        path.relative_to(sps_interfaces.VENDOR_ROOT)
        for path in sps_interfaces.VENDOR_ROOT.rglob("*")
        if path.is_file() and path.name != "upstream-manifest.json"
    }
    if source_files != vendor_files:
        raise sps_interfaces.InterfaceError("upstream and vendor file closures differ")
    for relative in source_files:
        if (source_dist / relative).read_bytes() != (
            sps_interfaces.VENDOR_ROOT / relative
        ).read_bytes():
            raise sps_interfaces.InterfaceError(f"interface bytes differ: {relative}")


def require_source_revision(
    manifest: dict[str, object], expected_source_revision: str
) -> None:
    actual = manifest.get("sourceRevision")
    if actual != expected_source_revision:
        raise sps_interfaces.InterfaceError(
            "requested source revision mismatch: "
            f"expected {expected_source_revision!r}, got {actual!r}"
        )


def update(
    source_dist: Path, source_manifest: Path, expected_source_revision: str
) -> None:
    manifest, registry = sps_interfaces.verify_distribution(source_dist, source_manifest)
    require_source_revision(manifest, expected_source_revision)
    parent = sps_interfaces.VENDOR_ROOT.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sps-interface-sync-", dir=parent) as temporary:
        temporary_root = Path(temporary)
        staged = temporary_root / "sps-rev4.1"
        staged_lock = temporary_root / "sps-interface.lock.json"
        old_vendor = temporary_root / "old-vendor"
        old_lock = temporary_root / "old-lock.json"
        failed_vendor = temporary_root / "failed-vendor"
        shutil.copytree(source_dist, staged)
        shutil.copy2(source_manifest, staged / "upstream-manifest.json")
        staged_lock.write_text(
            json.dumps(lock_value(manifest, registry), indent=2) + "\n",
            encoding="utf-8",
        )
        if sps_interfaces.LOCK_PATH.exists():
            shutil.copy2(sps_interfaces.LOCK_PATH, old_lock)
        installed = False
        try:
            if sps_interfaces.VENDOR_ROOT.exists():
                os.replace(sps_interfaces.VENDOR_ROOT, old_vendor)
            try:
                os.replace(staged, sps_interfaces.VENDOR_ROOT)
                installed = True
            except OSError:
                if old_vendor.exists():
                    os.replace(old_vendor, sps_interfaces.VENDOR_ROOT)
                raise
            os.replace(staged_lock, sps_interfaces.LOCK_PATH)
        except OSError:
            if installed and sps_interfaces.VENDOR_ROOT.exists():
                os.replace(sps_interfaces.VENDOR_ROOT, failed_vendor)
            if old_vendor.exists():
                os.replace(old_vendor, sps_interfaces.VENDOR_ROOT)
            if old_lock.exists():
                os.replace(old_lock, sps_interfaces.LOCK_PATH)
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", "--from", dest="source", required=True, type=Path)
    parser.add_argument("--expected-source-revision", required=True)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        source_dist, source_manifest = source_paths(arguments.source)
        manifest, _ = sps_interfaces.verify_distribution(source_dist, source_manifest)
        require_source_revision(manifest, arguments.expected_source_revision)
        if arguments.check:
            compare(source_dist, source_manifest)
            print("SPS Rev4.1 interfaces match the vendored snapshot")
        else:
            update(
                source_dist,
                source_manifest,
                arguments.expected_source_revision,
            )
            print(f"updated {sps_interfaces.VENDOR_ROOT}")
    except (OSError, sps_interfaces.InterfaceError, KeyError, TypeError) as error:
        raise SystemExit(f"SPS interface sync failed: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
