#!/usr/bin/env python3
"""One authoritative discovery layer for compiler-harness fixture material.

The readable unit is ``fixtures/<family>/<case>/``. Every case owns its primary
C/C++ translation unit, optional support translation units, and authoring
sidecars directly. A case-local ``candidate/`` directory holds a non-claimable
LLVM-17 candidate bundle.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import checkpoint_model


ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "fixtures"
SUPPORT_C_DIR = ROOT / "c"
INTEGRATION_DIR = ROOT / "integration"
RELEASE_BODY_FRAGMENTS_DIR = INTEGRATION_DIR / "Inputs" / "release-body-fragments"
LEGACY_ARTIFACTS_DIR = ROOT / "artifacts"
TRANSLATION_UNIT_SUFFIXES = frozenset({".c", ".cc", ".cpp", ".cxx"})


def fixture_case_dirs(root: Path = ROOT) -> list[Path]:
    """Return every directory containing a fixture snapshot."""
    return sorted(path.parent for path in (root / "fixtures").rglob("snapshot.yaml"))


def fixture_mlir_paths(root: Path = ROOT) -> list[Path]:
    return sorted((root / "fixtures").rglob("*.mlir"))


def case_source_paths(root: Path = ROOT) -> list[Path]:
    """Return C/C++ evidence owned directly by fixture cases."""
    return sorted(
        path
        for case_dir in fixture_case_dirs(root)
        for path in case_dir.iterdir()
        if path.suffix in TRANSLATION_UNIT_SUFFIXES and path.is_file()
    )


def fixture_source_paths(root: Path = ROOT) -> list[Path]:
    """Return every case-owned fixture translation unit."""
    return case_source_paths(root)


def release_fragment_paths(root: Path = ROOT) -> list[Path]:
    """Return integration-owned C fragments compiled with the fixture corpus."""
    return sorted(
        path
        for path in (
            root / "integration" / "Inputs" / "release-body-fragments"
        ).glob("*.c")
        if path.is_file()
    )


def provenance_c_sources(root: Path = ROOT) -> list[Path]:
    """Return translation units whose provenance is part of the fixture corpus."""
    return sorted([*fixture_source_paths(root), *release_fragment_paths(root)])


def compiler_c_sources(root: Path = ROOT) -> list[Path]:
    """Return every independently compiled input, including the shared driver."""
    return sorted([*provenance_c_sources(root), root / "c" / "equivalence_driver.c"])


def candidate_dirs(root: Path = ROOT) -> list[Path]:
    """Return candidate directories, including malformed ones for validation."""
    return sorted(
        path for path in (root / "fixtures").rglob("candidate") if path.is_dir()
    )


def candidate_spec_paths(root: Path = ROOT) -> list[Path]:
    return sorted((root / "fixtures").rglob("bundle-spec.json"))


def sole_case_mlir(case_dir: Path) -> Path:
    mlir = sorted(case_dir.glob("*.mlir"))
    if len(mlir) != 1:
        raise ValueError(f"{case_dir}: expected exactly one case-root MLIR file")
    return mlir[0]


def validate_candidate_location(candidate: Path, root: Path = ROOT) -> str | None:
    """Return a diagnostic when ``candidate`` is not at family/case depth."""
    try:
        relative = candidate.relative_to(root / "fixtures")
    except ValueError:
        return "candidate directory is outside fixtures/"
    if len(relative.parts) != 3 or relative.parts[-1] != "candidate":
        return "candidate must live at fixtures/<family>/<case>/candidate/"
    if not (candidate.parent / "snapshot.yaml").is_file():
        return "candidate has no sibling case snapshot.yaml"
    return None


def c_source_layout_errors(root: Path = ROOT) -> list[str]:
    """Diagnose fixture translation units outside the case-owned contract."""
    root = root.resolve()
    fixture_root = root / "fixtures"
    fragment_root = root / "integration" / "Inputs" / "release-body-fragments"
    owned_fragments = {path.resolve() for path in release_fragment_paths(root)}
    errors: list[str] = []
    case_dirs = fixture_case_dirs(root)
    case_set = set(case_dirs)

    if fixture_root.is_dir():
        for scenario in sorted(fixture_root.iterdir()):
            legacy = scenario / "sources"
            if os.path.lexists(legacy):
                errors.append(
                    f"{legacy.relative_to(root)}: family sources/ directories are forbidden"
                )

    for path in sorted(fixture_root.rglob("*")):
        if path.suffix not in TRANSLATION_UNIT_SUFFIXES:
            continue
        if path.parent not in case_set:
            errors.append(
                f"{path.relative_to(root)}: fixture translation unit must be directly "
                "owned by a snapshot case"
            )

    inode_owners: dict[tuple[int, int], Path] = {}
    for case_dir in case_dirs:
        units = sorted(
            path
            for path in case_dir.iterdir()
            if path.suffix in TRANSLATION_UNIT_SUFFIXES
            and (path.is_file() or path.is_symlink())
        )
        for path in units:
            if path.is_symlink():
                errors.append(
                    f"{path.relative_to(root)}: case-owned translation units must not be symlinks"
                )
                continue
            try:
                status = path.stat()
            except OSError as error:
                errors.append(f"{path.relative_to(root)}: cannot stat source: {error}")
                continue
            identity = (status.st_dev, status.st_ino)
            previous = inode_owners.get(identity)
            if previous is not None and previous != path:
                errors.append(
                    f"{path.relative_to(root)}: source is shared with {previous.relative_to(root)}"
                )
            else:
                inode_owners[identity] = path

        abi_path = case_dir / "abi.sps.yaml"
        policy_path = case_dir / "policy.sps.yaml"
        if not policy_path.is_file() or policy_path.is_symlink():
            errors.append(
                f"{policy_path.relative_to(root)}: every fixture case requires a local policy sidecar"
            )
        if not abi_path.is_file() or abi_path.is_symlink():
            errors.append(
                f"{abi_path.relative_to(root)}: every fixture case requires a local ABI sidecar"
            )
            primary: Path | None = None
        else:
            try:
                abi = checkpoint_model.strict_yaml_load(
                    abi_path.read_bytes(), source=str(abi_path)
                )
            except (OSError, checkpoint_model.CheckpointError) as error:
                errors.append(f"{abi_path.relative_to(root)}: {error}")
                primary = None
            else:
                if not isinstance(abi, dict):
                    errors.append(
                        f"{abi_path.relative_to(root)}: ABI sidecar must be a mapping"
                    )
                    primary = None
                    abi = {}
                source_name = abi.get("source")
                if (
                    not isinstance(source_name, str)
                    or Path(source_name).name != source_name
                    or Path(source_name).suffix not in TRANSLATION_UNIT_SUFFIXES
                ):
                    errors.append(
                        f"{abi_path.relative_to(root)}: source must be a local C/C++ basename"
                    )
                    primary = None
                else:
                    primary = case_dir / source_name
                    if primary not in units or not primary.is_file():
                        errors.append(
                            f"{abi_path.relative_to(root)}: primary source {source_name!r} "
                            "is not a local translation unit"
                        )

        snapshot_path = case_dir / "snapshot.yaml"
        try:
            snapshot = checkpoint_model.strict_yaml_load(
                snapshot_path.read_bytes(), source=str(snapshot_path)
            )
        except (OSError, checkpoint_model.CheckpointError) as error:
            errors.append(f"{snapshot_path.relative_to(root)}: {error}")
            continue
        if not isinstance(snapshot, dict):
            errors.append(
                f"{snapshot_path.relative_to(root)}: snapshot must be a mapping"
            )
            continue
        evidence = snapshot.get("c_evidence")
        if not isinstance(evidence, list) or any(
            not isinstance(item, str) for item in evidence
        ):
            errors.append(
                f"{snapshot_path.relative_to(root)}: c_evidence must list case-owned sources"
            )
            continue
        resolved_evidence: list[Path] = []
        for index, item in enumerate(evidence):
            try:
                resolved_evidence.append(
                    checkpoint_model.resolve_root_path(
                        root, item, f"c_evidence[{index}]"
                    )
                )
            except checkpoint_model.CheckpointError as error:
                errors.append(f"{snapshot_path.relative_to(root)}: {error}")
        expected = {path.resolve() for path in units if not path.is_symlink()}
        if set(resolved_evidence) != expected or len(resolved_evidence) != len(expected):
            errors.append(
                f"{snapshot_path.relative_to(root)}: c_evidence must exactly list every "
                "case-owned C/C++ translation unit"
            )
        if primary is not None and primary.resolve() not in set(resolved_evidence):
            errors.append(
                f"{snapshot_path.relative_to(root)}: c_evidence omits the ABI primary source"
            )

        expect = snapshot.get("expect")
        if not isinstance(expect, dict):
            errors.append(
                f"{snapshot_path.relative_to(root)}: expect must be a mapping"
            )
            continue
        pipelines = expect.get("pipelines")
        if not isinstance(pipelines, dict):
            errors.append(
                f"{snapshot_path.relative_to(root)}: expect.pipelines must be a mapping"
            )
            continue
        boundary = pipelines.get("source-boundary")
        if not isinstance(boundary, dict) or boundary.get("kind") != "diagnostic":
            errors.append(
                f"{snapshot_path.relative_to(root)}: expected one compact "
                "source-boundary diagnostic pipeline"
            )

    for path in sorted(fragment_root.rglob("*.c")):
        if path.is_file() and path.resolve() not in owned_fragments:
            errors.append(
                f"{path.relative_to(root)}: release-body C fragment must be "
                "directly owned by integration/Inputs/release-body-fragments/"
            )
    return errors


def _display_source(path: Path, relative_to: Path | None) -> str:
    if relative_to is None:
        return str(path.resolve())
    return os.path.relpath(path.resolve(), relative_to.resolve())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or list the compiler harness C source inventory"
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--relative-to", type=Path)
    parser.add_argument("--check-c-source-layout", action="store_true")
    parser.add_argument("--list-provenance-c-sources", action="store_true")
    arguments = parser.parse_args()
    if not (
        arguments.check_c_source_layout
        or arguments.list_provenance_c_sources
    ):
        parser.error(
            "select --check-c-source-layout or --list-provenance-c-sources"
        )

    root = arguments.root.resolve()
    errors = c_source_layout_errors(root)
    if errors:
        print("\n".join(f"error: {error}" for error in errors), file=sys.stderr)
        return 1
    if arguments.check_c_source_layout:
        print("C source layout checks passed")
    if arguments.list_provenance_c_sources:
        for source in provenance_c_sources(root):
            print(_display_source(source, arguments.relative_to))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
