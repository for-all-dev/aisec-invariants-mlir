#!/usr/bin/env python3
"""One authoritative discovery layer for compiler-harness fixture material.

The readable unit is ``fixtures/<family>/<case>/``. Family ``sources/``
directories hold C evidence shared by one or more cases, while a case-local
``candidate/`` directory holds a non-claimable LLVM-17 candidate bundle.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "fixtures"
SUPPORT_C_DIR = ROOT / "c"
INTEGRATION_DIR = ROOT / "integration"
RELEASE_BODY_FRAGMENTS_DIR = INTEGRATION_DIR / "Inputs" / "release-body-fragments"
LEGACY_ARTIFACTS_DIR = ROOT / "artifacts"


def fixture_case_dirs(root: Path = ROOT) -> list[Path]:
    """Return every directory containing a fixture snapshot."""
    return sorted(path.parent for path in (root / "fixtures").rglob("snapshot.yaml"))


def fixture_mlir_paths(root: Path = ROOT) -> list[Path]:
    return sorted((root / "fixtures").rglob("*.mlir"))


def family_source_paths(root: Path = ROOT) -> list[Path]:
    """Return family-owned C evidence, excluding support and integration C."""
    source_roots = (root / "fixtures").glob("*/sources")
    return sorted(
        path
        for source_root in source_roots
        for path in source_root.rglob("*.c")
        if path.is_file()
    )


def provenance_c_sources(root: Path = ROOT) -> list[Path]:
    """Return C files whose provenance headers are part of the fixture corpus."""
    fragments = (root / "integration" / "Inputs" / "release-body-fragments").glob("*.c")
    return sorted([*family_source_paths(root), *fragments])


def compiler_c_sources(root: Path = ROOT) -> list[Path]:
    """Return every independently compiled C input, including the shared driver."""
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
