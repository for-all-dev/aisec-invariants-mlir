#!/usr/bin/env python3
"""Update or verify the digest-locked SPS executable-reference snapshot.

The vendored tree is intentionally smaller than an SPS checkout.  It contains
the complete ``reference`` directory, the conformance profile used to count
fixture families, and the Rev4.1 interface builder used by the reference
runner.  Generated interface artifacts stay in the separately locked
``sps-rev4.1`` vendor.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any


HARNESS_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_ROOT = HARNESS_ROOT / "contracts"
VENDOR_ROOT = CONTRACT_ROOT / "vendor" / "sps-reference-rev4"
LOCK_PATH = CONTRACT_ROOT / "sps-reference.lock.json"
INTERFACE_LOCK_PATH = CONTRACT_ROOT / "sps-interface.lock.json"
PROFILE_PATH = "SPS_Rev4_LLVM_Normal_Form_and_Conformance_Profile.md"
BUILDER_PATH = "interfaces/rev4.1/build_interfaces.py"
LOCK_FORMAT = "SPS-Harness-Reference-Lock-v1"
CLAIM_BOUNDARY = "ExecutableReferenceOnly"
HEX_RE = re.compile(r"^[0-9a-f]{64}$")
FAMILY_RE = re.compile(r"NF-FX-[A-Z0-9-]+")


class ReferenceSyncError(ValueError):
    pass


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def load_json(path: Path) -> Any:
    def unique_object(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise ReferenceSyncError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReferenceSyncError(f"cannot read JSON {path}: {exc}") from exc


def material_files(root: Path, *, ignore_python_caches: bool = False) -> list[Path]:
    if not root.is_dir():
        raise ReferenceSyncError(f"reference root is not a directory: {root}")
    files = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            if ignore_python_caches:
                continue
            raise ReferenceSyncError(
                f"Python cache is forbidden in locked reference closure: {relative}"
            )
        if path.is_symlink():
            raise ReferenceSyncError(
                f"symlink is forbidden in reference closure: {relative}"
            )
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def source_files(source_root: Path) -> list[tuple[str, Path]]:
    source_root = source_root.resolve()
    required = [source_root / PROFILE_PATH, source_root / BUILDER_PATH]
    for path in required:
        if not path.is_file() or path.is_symlink():
            raise ReferenceSyncError(f"missing plain source file: {path}")
    reference_root = source_root / "reference"
    reference_files = material_files(reference_root, ignore_python_caches=True)
    if not reference_files:
        raise ReferenceSyncError(f"empty SPS reference directory: {reference_root}")
    rows = [(PROFILE_PATH, required[0]), (BUILDER_PATH, required[1])]
    rows.extend(
        ("reference/" + path.relative_to(reference_root).as_posix(), path)
        for path in reference_files
    )
    return sorted(rows)


def vendor_files() -> list[tuple[str, Path]]:
    return [
        (path.relative_to(VENDOR_ROOT).as_posix(), path)
        for path in material_files(VENDOR_ROOT)
    ]


def metadata_rows(files: list[tuple[str, Path]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for relative, path in files:
        raw = path.read_bytes()
        rows.append({"path": relative, "sha256": sha256(raw), "size": len(raw)})
    return rows


def reference_counts(root: Path) -> dict[str, int]:
    assurance = load_json(root / "reference" / "assurance-status.json")
    if not isinstance(assurance, dict) or set(assurance) != {
        "formatId",
        "claimBoundary",
        "claims",
        "refusals",
    }:
        raise ReferenceSyncError("reference assurance manifest has the wrong field set")
    if (
        assurance["formatId"] != "SPS-Reference-Assurance-Status-v2"
        or assurance["claimBoundary"] != CLAIM_BOUNDARY
    ):
        raise ReferenceSyncError(
            f"reference assurance identity and boundary must be {CLAIM_BOUNDARY}"
        )
    required_claims = {
        "normativeLLVMV2": "Open(NotImplemented)",
        "normativeInterfacesV2": "Open(SchemaAndVectorsOnly)",
        "normativePONF": "Open(ReferenceSliceOnly)",
        "writtenProofMechanization": "Open(NotMechanized)",
        "adaptiveInvocation": "Unknown(PersistentInvariantEncodingUnsupported)",
        "strongHostObserver": "Open(ObserverProfileNotModeled)",
        "p4Deployment": "Open(P4EvidenceProfileUnavailable)",
        "crossSolver": "Open(RequiresSecondInstalledSolver)",
    }
    claims = assurance["claims"]
    if not isinstance(claims, list):
        raise ReferenceSyncError("reference assurance claims must be a list")
    actual_claims: dict[str, str] = {}
    for index, row in enumerate(claims):
        if not isinstance(row, dict) or set(row) != {"claimId", "status"}:
            raise ReferenceSyncError(f"reference assurance claim {index} is malformed")
        claim_id = row["claimId"]
        status = row["status"]
        if not isinstance(claim_id, str) or not isinstance(status, str):
            raise ReferenceSyncError(f"reference assurance claim {index} is malformed")
        if claim_id in actual_claims:
            raise ReferenceSyncError(f"duplicate reference assurance claim: {claim_id}")
        if "Proved" in status or status.startswith("Closed"):
            raise ReferenceSyncError(f"unsafe closed reference assurance claim: {row}")
        actual_claims[claim_id] = status
    if actual_claims != required_claims:
        raise ReferenceSyncError("reference assurance claim inventory differs")
    if not isinstance(assurance["refusals"], list) or not assurance["refusals"]:
        raise ReferenceSyncError("reference assurance refusal inventory is empty")
    catalog = load_json(root / "reference" / "fixture-catalog.json")
    if not isinstance(catalog, dict) or not isinstance(catalog.get("cases"), list):
        raise ReferenceSyncError("reference fixture catalog has no case list")
    cases = catalog["cases"]
    fixture_names: list[str] = []
    families: set[str] = set()
    case_ids: set[str] = set()
    for index, row in enumerate(cases):
        if not isinstance(row, dict):
            raise ReferenceSyncError(f"fixture catalog row {index} is not an object")
        filename = row.get("file")
        family = row.get("familyId")
        case_id = row.get("caseId")
        if not all(
            isinstance(value, str) and value
            for value in (filename, family, case_id)
        ):
            raise ReferenceSyncError(f"fixture catalog row {index} is malformed")
        if case_id in case_ids:
            raise ReferenceSyncError(f"duplicate fixture caseId: {case_id}")
        case_ids.add(case_id)
        fixture_names.append(filename)
        families.add(family)
    fixture_root = root / "reference" / "fixtures"
    actual_fixtures = sorted(
        path.relative_to(fixture_root).as_posix()
        for path in fixture_root.rglob("*")
        if path.is_file() or path.is_symlink()
    )
    if sorted(fixture_names) != actual_fixtures or len(fixture_names) != len(
        set(fixture_names)
    ):
        raise ReferenceSyncError("fixture catalog and fixture file closure differ")
    unit_tests = 0
    for path in sorted((root / "reference" / "tests").glob("test*.py")):
        try:
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise ReferenceSyncError(f"cannot inspect reference tests: {exc}") from exc
        unit_tests += sum(
            1
            for node in module.body
            if isinstance(node, ast.ClassDef)
            for member in node.body
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            and member.name.startswith("test_")
        )
    if unit_tests == 0:
        raise ReferenceSyncError("reference unit-test inventory is empty")
    profile_text = (root / PROFILE_PATH).read_text(encoding="utf-8")
    profile_families = set(FAMILY_RE.findall(profile_text))
    if not families.issubset(profile_families):
        raise ReferenceSyncError("executable fixture family is absent from the profile")
    return {
        "fixtureCases": len(cases),
        "unitTests": unit_tests,
        "executableFamilies": len(families),
        "profileFamilies": len(profile_families),
    }


def lock_value(root: Path, files: list[tuple[str, Path]]) -> dict[str, object]:
    rows = metadata_rows(files)
    try:
        interface_lock_raw = INTERFACE_LOCK_PATH.read_bytes()
    except OSError as exc:
        raise ReferenceSyncError(f"cannot read interface lock: {exc}") from exc
    return {
        "formatId": LOCK_FORMAT,
        "claimBoundary": CLAIM_BOUNDARY,
        "treeSha256": sha256(canonical_bytes(rows)),
        "interfaceLockSha256": sha256(interface_lock_raw),
        "counts": reference_counts(root),
        "files": rows,
    }


def validate_lock_shape(lock: Any) -> list[dict[str, object]]:
    expected_keys = {
        "formatId",
        "claimBoundary",
        "treeSha256",
        "interfaceLockSha256",
        "counts",
        "files",
    }
    if not isinstance(lock, dict) or set(lock) != expected_keys:
        raise ReferenceSyncError("reference lock has the wrong field set")
    if lock["formatId"] != LOCK_FORMAT or lock["claimBoundary"] != CLAIM_BOUNDARY:
        raise ReferenceSyncError(
            "reference lock has an unsafe identity or claim boundary"
        )
    for field in ("treeSha256", "interfaceLockSha256"):
        if not isinstance(lock[field], str) or HEX_RE.fullmatch(lock[field]) is None:
            raise ReferenceSyncError(f"reference lock has malformed {field}")
    rows = lock["files"]
    if not isinstance(rows, list):
        raise ReferenceSyncError("reference lock files must be a list")
    paths: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size"}:
            raise ReferenceSyncError(f"reference lock file row {index} is malformed")
        path = row["path"]
        digest = row["sha256"]
        size = row["size"]
        if (
            not isinstance(path, str)
            or not path
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or not isinstance(digest, str)
            or HEX_RE.fullmatch(digest) is None
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            raise ReferenceSyncError(f"reference lock file row {index} is malformed")
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ReferenceSyncError("reference lock paths must be sorted and unique")
    return rows


def verify_vendor() -> dict[str, object]:
    lock = load_json(LOCK_PATH)
    rows = validate_lock_shape(lock)
    files = vendor_files()
    actual_paths = [relative for relative, _ in files]
    locked_paths = [str(row["path"]) for row in rows]
    if actual_paths != locked_paths:
        raise ReferenceSyncError(
            "vendored reference file closure differs: "
            f"locked={locked_paths}, actual={actual_paths}"
        )
    for row, (_, path) in zip(rows, files, strict=True):
        raw = path.read_bytes()
        if len(raw) != row["size"] or sha256(raw) != row["sha256"]:
            raise ReferenceSyncError(f"vendored reference bytes differ: {row['path']}")
    if sha256(canonical_bytes(rows)) != lock["treeSha256"]:
        raise ReferenceSyncError("reference lock tree digest mismatch")
    if sha256(INTERFACE_LOCK_PATH.read_bytes()) != lock["interfaceLockSha256"]:
        raise ReferenceSyncError("reference lock interface-lock digest mismatch")
    expected = lock_value(VENDOR_ROOT, files)
    if lock != expected:
        raise ReferenceSyncError("reference lock metadata or counts differ")
    if LOCK_PATH.read_bytes() != pretty_bytes(expected):
        raise ReferenceSyncError("reference lock bytes are not canonical pretty JSON")
    return lock


def compare_source(source_root: Path, lock: dict[str, object]) -> None:
    source = source_files(source_root)
    vendor = vendor_files()
    source_paths = [relative for relative, _ in source]
    vendor_paths = [relative for relative, _ in vendor]
    if source_paths != vendor_paths:
        raise ReferenceSyncError(
            f"upstream and vendored reference file closures differ: "
            f"upstream={source_paths}, vendor={vendor_paths}"
        )
    for (relative, source_path), (_, vendor_path) in zip(
        source, vendor, strict=True
    ):
        if source_path.read_bytes() != vendor_path.read_bytes():
            raise ReferenceSyncError(
                f"upstream and vendored reference bytes differ: {relative}"
            )
    if lock_value(source_root.resolve(), source) != lock:
        raise ReferenceSyncError(
            "upstream reference does not reproduce the installed lock"
        )


def update(source_root: Path) -> None:
    source_root = source_root.resolve()
    files = source_files(source_root)
    value = lock_value(source_root, files)
    parent = VENDOR_ROOT.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="sps-reference-sync-", dir=parent
    ) as temporary:
        temporary_root = Path(temporary)
        staged_vendor = temporary_root / VENDOR_ROOT.name
        staged_lock = temporary_root / LOCK_PATH.name
        old_vendor = temporary_root / "old-vendor"
        old_lock = temporary_root / "old-lock.json"
        failed_vendor = temporary_root / "failed-vendor"
        failed_lock = temporary_root / "failed-lock.json"
        for relative, source_path in files:
            target = staged_vendor / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)
        staged_files = [
            (relative, staged_vendor / relative) for relative, _ in files
        ]
        if lock_value(staged_vendor, staged_files) != value:
            raise ReferenceSyncError(
                "staged reference changed while it was being copied"
            )
        staged_lock.write_bytes(pretty_bytes(value))
        if LOCK_PATH.exists():
            shutil.copy2(LOCK_PATH, old_lock)
        vendor_installed = False
        lock_installed = False
        try:
            if VENDOR_ROOT.exists():
                os.replace(VENDOR_ROOT, old_vendor)
            os.replace(staged_vendor, VENDOR_ROOT)
            vendor_installed = True
            os.replace(staged_lock, LOCK_PATH)
            lock_installed = True
            verify_vendor()
        except Exception:
            if vendor_installed and VENDOR_ROOT.exists():
                os.replace(VENDOR_ROOT, failed_vendor)
            if old_vendor.exists():
                os.replace(old_vendor, VENDOR_ROOT)
            if old_lock.exists():
                if LOCK_PATH.exists():
                    os.replace(LOCK_PATH, failed_lock)
                os.replace(old_lock, LOCK_PATH)
            elif lock_installed and LOCK_PATH.exists():
                os.replace(LOCK_PATH, failed_lock)
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        help="SPS root containing reference/, the profile, and interfaces/",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the installed vendor and optionally compare --source",
    )
    arguments = parser.parse_args()
    try:
        if arguments.check:
            lock = verify_vendor()
            configured_source = os.environ.get("SPS_REFERENCE_ROOT", "")
            source = arguments.source
            if source is None and configured_source:
                source = Path(configured_source)
            if source is not None:
                compare_source(source, lock)
                print(
                    "SPS executable reference source comparison: "
                    f"PERFORMED ({source.resolve()})"
                )
            else:
                print(
                    "SPS executable reference source comparison: "
                    "SKIPPED (SPS_REFERENCE_ROOT unset)"
                )
            counts = lock["counts"]
            print(
                "verified SPS executable reference vendor: "
                f"boundary={CLAIM_BOUNDARY} tree={lock['treeSha256']} "
                f"cases={counts['fixtureCases']} tests={counts['unitTests']} "
                f"families={counts['executableFamilies']}/{counts['profileFamilies']}"
            )
        else:
            if arguments.source is None:
                parser.error("--source is required unless --check is used")
            update(arguments.source)
            print(f"updated {VENDOR_ROOT}")
    except (OSError, UnicodeError, ReferenceSyncError, KeyError, TypeError) as exc:
        raise SystemExit(f"SPS reference sync failed: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
