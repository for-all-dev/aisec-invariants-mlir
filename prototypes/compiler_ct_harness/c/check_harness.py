#!/usr/bin/env python3
"""Dependency-free structural checks for the C/MLIR confidentiality corpus."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
C_DIR = ROOT / "c"
MLIR_DIR = ROOT / "mlir"

PROVENANCE_FIELDS = (
    "Case:",
    "Reduction classification:",
    "Relationship to upstream:",
    "Secret inputs:",
    "Public inputs:",
    "Canonical compiler command:",
    "License note:",
)

MLIR_FIELDS = (
    "// case:",
    "// classification:",
    "// c source:",
    "// upstream GitHub source:",
    "// secret:",
    "// public:",
    "// expected verdict:",
    "// exact incident boundary:",
)

ERROR_BLOCK = re.compile(
    r"(?m)^\s*// CONFIDENTIALITY ERROR: .+\n"
    r"\s*// secret source: .+\n"
    r"\s*// observable effect: .+\n"
    r"\s*// reason: .+\n"
    r"\s*// detection boundary: .+\n"
    r"\s*(?!//)(?:[%^}]|[a-zA-Z]).+"
)

REPAIR_BLOCK = re.compile(
    r"(?m)^\s*// CONFIDENTIALITY REPAIR: .+\n"
    r"\s*// secret source: .+\n"
    r"\s*// (?:removed observable|safe effect): .+\n"
    r"\s*// reason: .+\n"
    r"\s*// detection boundary: .+\n"
    r"\s*(?!//)(?:[%^}]|[a-zA-Z]).+"
)


def fail(errors: list[str], path: Path, message: str) -> None:
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def c_sources() -> list[Path]:
    return sorted(
        path
        for path in C_DIR.glob("*.c")
        if path.name != "equivalence_driver.c"
    )


def check_provenance() -> list[str]:
    errors: list[str] = []
    mutable = re.compile(r"github\.com/[^/]+/[^/]+/(?:blob|tree)/(?:main|master)(?:/|$)")
    github_revision = re.compile(
        r"github\.com/[^/]+/[^/]+/(?:blob|tree)/([^/#?]+)(?:/|$)"
    )

    for path in c_sources():
        text = path.read_text()
        for field in PROVENANCE_FIELDS:
            if field not in text:
                fail(errors, path, f"missing provenance field {field!r}")

        has_original = "Original vulnerable code:" in text
        declares_none = re.search(
            r"Original C source:\s*\n\s*\*\s+none\b", text, re.IGNORECASE
        )
        if not has_original and not declares_none:
            fail(
                errors,
                path,
                "must link Original vulnerable code or declare Original C source: none",
            )

        for url in re.findall(r"https://[^\s*)]+", text):
            clean_url = url.rstrip(".,")
            if mutable.search(clean_url):
                fail(errors, path, f"mutable GitHub URL {clean_url}")
            match = github_revision.search(clean_url)
            if match and not re.fullmatch(r"[0-9a-f]{40}", match.group(1)):
                fail(errors, path, f"GitHub blob/tree URL lacks a full commit: {clean_url}")

        classification_match = re.search(
            r"Reduction classification:\s*\n\s*\*\s+([^\n]+)", text
        )
        classification = classification_match.group(1).strip() if classification_match else ""
        if declares_none and classification in {
            "faithful-minimal-reduction",
            "adapted-upstream-snippet",
        }:
            fail(errors, path, "claims an upstream-C reduction after declaring no C source")

    return errors


def is_bad(path: Path) -> bool:
    return any(marker in path.name for marker in (".bad.mlir", "_bad.mlir", "lowered_bad", "target_bad"))


def is_fixed(path: Path) -> bool:
    return any(marker in path.name for marker in (".fixed.mlir", "_fixed.mlir", "lowered_fixed", "target_fixed"))


def check_annotations() -> list[str]:
    errors: list[str] = []
    for path in sorted(MLIR_DIR.glob("*.mlir")):
        text = path.read_text()
        for field in MLIR_FIELDS:
            if field not in text:
                fail(errors, path, f"missing MLIR header field {field!r}")

        if "CONFIDENTIALITY BREAK" in text:
            fail(errors, path, "uses obsolete CONFIDENTIALITY BREAK marker")

        if is_bad(path):
            if not ERROR_BLOCK.search(text):
                fail(errors, path, "lacks a complete error block adjacent to an MLIR op")
        elif "CONFIDENTIALITY ERROR:" in text:
            fail(errors, path, "non-bad fixture contains a confidentiality error block")

        if is_fixed(path):
            if "CONFIDENTIALITY ERROR:" in text:
                fail(errors, path, "fixed fixture contains a confidentiality error")
            if not REPAIR_BLOCK.search(text):
                fail(errors, path, "lacks a complete repair block adjacent to an MLIR op")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "check", choices=("provenance", "annotations", "all"), default="all", nargs="?"
    )
    args = parser.parse_args()

    errors: list[str] = []
    if args.check in ("provenance", "all"):
        errors.extend(check_provenance())
    if args.check in ("annotations", "all"):
        errors.extend(check_annotations())

    if errors:
        print("\n".join(f"error: {message}" for message in errors), file=sys.stderr)
        return 1

    print(f"{args.check} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
