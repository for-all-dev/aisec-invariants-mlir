#!/usr/bin/env python3
"""Structural checks for SPS preflight fixtures and candidate bitcode bundles.

MLIR files in ``mlir/`` are deliberately shape-only.  They do not carry a
ModelStatus. Non-claimable future oracles live beside LLVM-17 candidate
``artifact.bc`` files under ``artifacts/``. They preserve the normative result
domains without pretending that the prototype descriptors are Rev4 interfaces.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
C_DIR = ROOT / "c"
MLIR_DIR = ROOT / "mlir"
ARTIFACTS_DIR = ROOT / "artifacts"
SHAPE_MANIFEST = ROOT / "contracts" / "shape-fixtures.json"
CONFORMANCE_MATRIX = ROOT / "contracts" / "rev4-conformance-matrix.json"

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
    "// entry:",
    "// classification:",
    "// c source:",
    "// upstream GitHub source:",
    "// upstream revision:",
    "// secret:",
    "// public:",
    "// diagnostic focus:",
    "// evidence boundary:",
)

LEGACY_RESULT_FIELDS = (
    "// expected outcome:",
    "// expected verdict:",
    "// observer/model:",
    "// reason id:",
    "// outstanding obligations:",
    "// result rows:",
    "// target tuple:",
    "// l1 disposition:",
)

CLASSIFICATIONS = frozenset(
    {
        "compiler-generated-minimized",
        "modeled-from-verified-assembly",
        "modeled-fixed-target",
        "modeled-helper-call-without-contract",
        "modeled-test-profile",
        "seeded-semantic-harness",
        "reduced-runtime-model",
    }
)

MODEL_STATUS = frozenset({"Proved", "Counterexample", "Unknown"})
DEPLOYMENT_STATUS = frozenset({"Open", "Closed"})
POLICY_STATUS = frozenset({"Complete", "Findings", "Incomplete"})
PRODUCT_DISPOSITION = frozenset({"ProductSafe", "ReplayableCounterexample", "Blocked"})
IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
EVIDENCE_LEVEL = re.compile(r"\bL[0-4]\b")
COALITION = re.compile(r"\{(?:[a-z][a-z0-9-]*(?:,[a-z][a-z0-9-]*)*)?\}\Z")
REQUIRED_CONFORMANCE_IDS = {
    *(f"NF-A{index:02d}" for index in range(1, 16)),
    *(f"NF-CM{index:02d}" for index in range(1, 13)),
}

# Each bundle contains the theorem-facing form of a corrected MLIR shape seed.
SEMANTIC_BUNDLES = {
    "abi_alias_disjoint.control.mlir": "abi-alias-disjoint",
    "abi_alias_mayalias_overlap.bad.mlir": "abi-alias-mayalias-overlap",
    "abi_alias_missing_binding.unknown.mlir": "abi-alias-missing-binding",
    "alloca_size_high_count.unknown.mlir": "alloca-size-high",
    "alloca_size_public.control.mlir": "alloca-size-public",
    "audience_mismatch.bad.mlir": "audience-mismatch",
    "bound_exhausted_loop.unknown.mlir": "bound-exhausted-public",
    "bound_secret_trip_count.bad.mlir": "bound-secret-trip-count",
    "launder_scan.model_proved.p4_open.mlir": "launder-scan",
}

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


def split_llvm_arguments(arguments: str) -> list[str]:
    """Split the simple and aggregate LLVM parameter spellings at top level."""
    if not arguments.strip():
        return []
    parts: list[str] = []
    start = 0
    depth = 0
    quoted = False
    escaped = False
    for index, character in enumerate(arguments):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character in "([{<":
            depth += 1
        elif character in ")]}>":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(arguments[start:index].strip())
            start = index + 1
    parts.append(arguments[start:].strip())
    return parts


def llvm_functions(llvm_ir: str, name: str) -> list[dict[str, object]]:
    """Return declaration/definition signatures and definition bodies for name."""
    header = re.compile(
        rf"(?m)^(?P<kind>define|declare)\s+(?P<prefix>[^@\n]+)"
        rf"@{re.escape(name)}\s*\((?P<arguments>[^)]*)\)(?P<suffix>[^\n]*)"
    )
    functions: list[dict[str, object]] = []
    for match in header.finditer(llvm_ir):
        prefix = match.group("prefix").strip()
        result_type = prefix.split()[-1] if prefix else ""
        parameters = [
            parameter.split()[0] if parameter.split() else ""
            for parameter in split_llvm_arguments(match.group("arguments"))
        ]
        body = ""
        if match.group("kind") == "define":
            opening = llvm_ir.find("{", match.start(), match.end())
            closing = llvm_ir.find("\n}", opening)
            if opening >= 0 and closing >= 0:
                body = llvm_ir[opening + 1 : closing]
        functions.append(
            {
                "kind": match.group("kind"),
                "result": result_type,
                "parameters": parameters,
                "body": body,
            }
        )
    return functions


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(errors: list[str], path: Path, message: str) -> None:
    try:
        label = path.relative_to(ROOT)
    except ValueError:
        label = path
    errors.append(f"{label}: {message}")


def field_values(text: str, field: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(rf"(?m)^\s*{re.escape(field)}\s*(.*?)\s*$", text)
    ]


def c_sources() -> list[Path]:
    return sorted(path for path in C_DIR.glob("*.c") if path.name != "equivalence_driver.c")


def check_provenance() -> list[str]:
    errors: list[str] = []
    mutable = re.compile(r"github\.com/[^/]+/[^/]+/(?:blob|tree)/(?:main|master)(?:/|$)")
    revision = re.compile(r"github\.com/[^/]+/[^/]+/(?:blob|tree)/([^/#?]+)(?:/|$)")

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
            fail(errors, path, "must link Original vulnerable code or declare Original C source: none")

        for url in re.findall(r"https://[^\s*)]+", text):
            clean = url.rstrip(".,")
            if mutable.search(clean):
                fail(errors, path, f"mutable GitHub URL {clean}")
            match = revision.search(clean)
            if match and not re.fullmatch(r"[0-9a-f]{40}", match.group(1)):
                fail(errors, path, f"GitHub blob/tree URL lacks a full commit: {clean}")

    return errors


def required_capabilities(name: str) -> list[str]:
    caps = {"canonical-bitcode-v1", "policy-binding-v1", "whole-entry-product-v1"}
    lowered = name.lower()
    if any(token in lowered for token in ("alias", "offset", "overwritten", "leftover", "redis")):
        caps.update({"byte-memory-v1", "alias-v1"})
    if any(token in lowered for token in ("release", "audience", "error_oracle", "ckks")):
        caps.update({"release-ledger-v1", "coalition-audience-v1"})
    if any(token in lowered for token in ("wrong_party", "wrong_host")):
        caps.add("coalition-audience-v1")
    if any(token in lowered for token in ("precision", "predecessor", "bound", "alloca")):
        caps.add("relational-v1")
    if any(token in lowered for token in ("kyberslash", "clangover", "wolfssl", "launder")):
        caps.add("final-binary-p4-v1")
    return sorted(caps)


def shape_record(path: Path) -> dict[str, object]:
    text = path.read_text()
    entries = field_values(text, "// entry:")
    entry = entries[0] if len(entries) == 1 else "<invalid>"
    focus = field_values(text, "// diagnostic focus:")
    classification = field_values(text, "// classification:")
    return {
        "sha256": digest(path),
        "scope": "preflight-only",
        "entry": entry,
        "classification": classification[0] if len(classification) == 1 else "<invalid>",
        "diagnostic_focus": focus[0] if len(focus) == 1 else "<invalid>",
        "semantic_bundle": SEMANTIC_BUNDLES.get(path.name),
        "pending_capabilities": required_capabilities(path.name),
    }


def shape_manifest_snapshot() -> dict[str, object]:
    return {
        "schema_version": "sps-shape-manifest-v1",
        "scope": "preflight-only",
        "fixed_observation_model": "Theta_ct",
        "model_status_authoritative": False,
        "fixtures": {
            path.name: shape_record(path) for path in sorted(MLIR_DIR.glob("*.mlir"))
        },
    }


def write_shape_manifest() -> None:
    SHAPE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    SHAPE_MANIFEST.write_text(json.dumps(shape_manifest_snapshot(), indent=2, sort_keys=True) + "\n")


def check_shape_manifest() -> list[str]:
    errors: list[str] = []
    if not SHAPE_MANIFEST.is_file():
        fail(errors, SHAPE_MANIFEST, "missing; run check_harness.py update-manifest")
        return errors
    try:
        actual = json.loads(SHAPE_MANIFEST.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(errors, SHAPE_MANIFEST, f"cannot parse: {error}")
        return errors
    expected = shape_manifest_snapshot()
    if actual != expected:
        fail(errors, SHAPE_MANIFEST, "stale or incomplete; run check_harness.py update-manifest")
    return errors


def check_annotations() -> list[str]:
    errors: list[str] = []
    for path in sorted(MLIR_DIR.glob("*.mlir")):
        text = path.read_text()
        values: dict[str, str] = {}
        for field in MLIR_FIELDS:
            found = field_values(text, field)
            if len(found) != 1 or not found[0]:
                fail(errors, path, f"MLIR header field {field!r} must occur once and be nonempty")
            else:
                values[field] = found[0]

        for field in LEGACY_RESULT_FIELDS:
            if field_values(text, field):
                fail(errors, path, f"legacy result field {field!r} belongs in a bundle sidecar")
        if "--verify-diagnostics" in text or "expected-error @" in text:
            fail(errors, path, "shape fixture contains an unimplemented semantic diagnostic oracle")

        classification = values.get("// classification:")
        if classification and classification not in CLASSIFICATIONS:
            fail(errors, path, "unknown classification")
        focus = values.get("// diagnostic focus:")
        if focus and not IDENTIFIER.fullmatch(focus):
            fail(errors, path, "diagnostic focus must be one lower-kebab identifier")
        boundary = values.get("// evidence boundary:")
        if boundary and not EVIDENCE_LEVEL.search(boundary):
            fail(errors, path, "evidence boundary must name L0 through L4")

        entry = shape_record(path)["entry"]
        if entry == "<invalid>" or f"llvm.func @{entry}" not in text:
            fail(errors, path, "entry must name a function in the file")
        elif f"// CHECK-LABEL: llvm.func @{entry}" not in text:
            fail(errors, path, "entry must have a matching CHECK-LABEL")

        c_source = values.get("// c source:")
        if c_source:
            candidate = (MLIR_DIR / c_source).resolve()
            try:
                candidate.relative_to(C_DIR.resolve())
            except ValueError:
                fail(errors, path, "c source must resolve inside c/")
            else:
                if candidate.suffix != ".c" or not candidate.is_file():
                    fail(errors, path, f"c source does not exist: {c_source}")

        if re.search(r"sps\.alias\s*=", text):
            fail(errors, path, "self-authoritative sps.alias is forbidden; use alias_candidate + ABI sidecar")
        if "sps.world_structural_size" in text:
            fail(errors, path, "self-authoritative world-structural binding is forbidden")

        error_count = text.count("CONFIDENTIALITY ERROR:")
        repair_count = text.count("CONFIDENTIALITY REPAIR:")
        if len(ERROR_BLOCK.findall(text)) != error_count:
            fail(errors, path, "has an incomplete or non-adjacent confidentiality error block")
        if len(REPAIR_BLOCK.findall(text)) != repair_count:
            fail(errors, path, "has an incomplete or non-adjacent confidentiality repair block")

    errors.extend(check_shape_manifest())
    return errors


def read_json(errors: list[str], path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(errors, path, f"cannot parse JSON: {error}")
        return None
    if not isinstance(value, dict):
        fail(errors, path, "top-level JSON value must be an object")
        return None
    return value


def coalition_members(errors: list[str], path: Path, value: object) -> tuple[str, ...] | None:
    if not isinstance(value, str) or not COALITION.fullmatch(value):
        fail(errors, path, f"invalid coalition {value!r}")
        return None
    members = () if value == "{}" else tuple(value[1:-1].split(","))
    if tuple(sorted(set(members))) != members:
        fail(errors, path, f"coalition must be sorted and duplicate-free: {value}")
        return None
    return members


def expected_coalitions(errors: list[str], path: Path, policy: dict[str, object]) -> set[tuple[str, ...]]:
    principals = policy.get("principals")
    maxima = policy.get("maximal_adversary_coalitions")
    if not isinstance(principals, list) or any(not isinstance(item, str) for item in principals):
        fail(errors, path, "principals must be an array of identifiers")
        return set()
    if principals != sorted(set(principals)):
        fail(errors, path, "principals must be sorted and duplicate-free")
    if any(not IDENTIFIER.fullmatch(item) for item in principals):
        fail(errors, path, "principals must use lower-kebab identifiers")
    if not isinstance(maxima, list) or not maxima:
        fail(errors, path, "maximal_adversary_coalitions must be a nonempty array")
        return set()
    closure: set[tuple[str, ...]] = set()
    normalized_maxima: list[tuple[str, ...]] = []
    for maximum in maxima:
        if not isinstance(maximum, list) or any(not isinstance(item, str) for item in maximum):
            fail(errors, path, "each maximal coalition must be an array of identifiers")
            continue
        normalized = tuple(maximum)
        if tuple(sorted(set(normalized))) != normalized:
            fail(errors, path, "maximal coalitions must be sorted and duplicate-free")
            continue
        if any(member not in principals for member in normalized):
            fail(errors, path, "maximal coalition contains an undeclared principal")
            continue
        normalized_maxima.append(normalized)
        for size in range(len(normalized) + 1):
            closure.update(itertools.combinations(normalized, size))
    if len(normalized_maxima) != len(set(normalized_maxima)):
        fail(errors, path, "maximal coalition list contains duplicates")
    for left, right in itertools.permutations(normalized_maxima, 2):
        if set(left) < set(right):
            fail(errors, path, f"maximal coalitions are not an antichain: {left} is below {right}")
            break
    return closure


def check_status_record(
    errors: list[str], path: Path, oracle: dict[str, object], policy: dict[str, object]
) -> None:
    model = oracle.get("model_status")
    deployment = oracle.get("deployment_status")
    policy_review = oracle.get("policy_review_status")
    rows = oracle.get("product_rows")
    blockers = oracle.get("global_blockers")
    if not isinstance(model, dict) or model.get("kind") not in MODEL_STATUS:
        fail(errors, path, "invalid model_status domain")
    elif model.get("kind") == "Counterexample" and model.get("witness") != "required-replayable":
        fail(errors, path, "Counterexample must require a replayable witness")
    elif model.get("kind") == "Unknown" and not model.get("reason"):
        fail(errors, path, "Unknown requires a reason")
    if not isinstance(deployment, dict) or deployment.get("kind") not in DEPLOYMENT_STATUS:
        fail(errors, path, "invalid deployment_status domain")
    elif deployment.get("kind") == "Open" and not deployment.get("obligations"):
        fail(errors, path, "Open deployment status requires obligations")
    elif deployment.get("kind") == "Closed" and not deployment.get("p4_evidence_bundle"):
        fail(errors, path, "Closed deployment status requires a P4EvidenceBundle")
    if not isinstance(policy_review, dict) or policy_review.get("kind") not in POLICY_STATUS:
        fail(errors, path, "invalid policy_review_status domain")
    elif policy_review.get("kind") == "Findings" and not policy_review.get("findings"):
        fail(errors, path, "Findings policy status requires findings")
    elif policy_review.get("kind") == "Incomplete" and not policy_review.get("reason"):
        fail(errors, path, "Incomplete policy status requires a reason")
    if not isinstance(blockers, list) or any(not isinstance(item, str) for item in blockers):
        fail(errors, path, "global_blockers must be an array of stable reasons")
        blockers = []
    if not isinstance(rows, list) or not rows:
        fail(errors, path, "product_rows must be a nonempty array")
        return
    seen: set[tuple[str, ...]] = set()
    dispositions: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            fail(errors, path, "coalition row must be an object")
            continue
        coalition = row.get("coalition")
        members = coalition_members(errors, path, coalition)
        if members is None:
            pass
        elif members in seen:
            fail(errors, path, f"duplicate coalition {coalition}")
        else:
            seen.add(members)
        disposition = row.get("product_disposition")
        if disposition not in PRODUCT_DISPOSITION:
            fail(errors, path, f"invalid product disposition for {coalition}")
        else:
            dispositions.append(str(disposition))
        if disposition == "ReplayableCounterexample" and row.get("replay") != "required":
            fail(errors, path, f"counterexample row {coalition} lacks replay requirement")
        if disposition == "Blocked" and not row.get("reason"):
            fail(errors, path, f"blocked row {coalition} lacks a reason")
    required_rows = expected_coalitions(errors, path, policy)
    if seen != required_rows:
        missing = sorted(required_rows - seen)
        extra = sorted(seen - required_rows)
        fail(errors, path, f"coalition rows are not the exact downward closure; missing={missing}, extra={extra}")
    if isinstance(model, dict) and dispositions:
        aggregate = (
            "Counterexample"
            if "ReplayableCounterexample" in dispositions
            else "Unknown" if blockers or "Blocked" in dispositions else "Proved"
        )
        if model.get("kind") != aggregate:
            fail(errors, path, f"future oracle ModelStatus is inconsistent with blockers/product rows; expected {aggregate}")


def check_conformance_matrix() -> list[str]:
    errors: list[str] = []
    matrix = read_json(errors, CONFORMANCE_MATRIX)
    if matrix is None:
        return errors
    if matrix.get("schema_version") != "sps-rev4-conformance-matrix-v1":
        fail(errors, CONFORMANCE_MATRIX, "unsupported schema_version")
    cases = matrix.get("cases")
    if not isinstance(cases, list):
        fail(errors, CONFORMANCE_MATRIX, "cases must be an array")
        return errors
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != len(cases) or len(ids) != len(set(ids)):
        fail(errors, CONFORMANCE_MATRIX, "case ids must be present and unique")
        return errors
    if set(ids) != REQUIRED_CONFORMANCE_IDS:
        fail(errors, CONFORMANCE_MATRIX, "must enumerate exactly NF-A01..15 and NF-CM01..12")
    allowed = {"pending", "infrastructure-seed", "preflight-seed"}
    for case in cases:
        if not isinstance(case, dict):
            continue
        if case.get("harness_status") not in allowed:
            fail(errors, CONFORMANCE_MATRIX, f"{case.get('id')}: invalid harness_status")
        if not case.get("expected"):
            fail(errors, CONFORMANCE_MATRIX, f"{case.get('id')}: expected disposition is required")
        seeds = case.get("seeds")
        if not isinstance(seeds, list) or any(not isinstance(seed, str) for seed in seeds):
            fail(errors, CONFORMANCE_MATRIX, f"{case.get('id')}: seeds must be an array of paths")
            continue
        if case.get("harness_status") != "pending" and not seeds:
            fail(errors, CONFORMANCE_MATRIX, f"{case.get('id')}: non-pending row requires seeds")
        for seed in seeds:
            candidate = (ROOT / seed).resolve()
            try:
                candidate.relative_to(ROOT.resolve())
            except ValueError:
                fail(errors, CONFORMANCE_MATRIX, f"{case.get('id')}: seed escapes harness: {seed}")
            else:
                if not candidate.exists():
                    fail(errors, CONFORMANCE_MATRIX, f"{case.get('id')}: missing seed: {seed}")
    return errors


def check_artifacts() -> list[str]:
    errors: list[str] = []
    expected_dirs = set(SEMANTIC_BUNDLES.values())
    actual_dirs = {path.name for path in ARTIFACTS_DIR.iterdir() if path.is_dir()} if ARTIFACTS_DIR.exists() else set()
    for name in sorted(expected_dirs - actual_dirs):
        fail(errors, ARTIFACTS_DIR / name, "required semantic bundle is missing")
    for name in sorted(actual_dirs - expected_dirs):
        fail(errors, ARTIFACTS_DIR / name, "bundle is not referenced by a shape fixture")

    for name in sorted(expected_dirs & actual_dirs):
        directory = ARTIFACTS_DIR / name
        required = (
            "artifact.bc",
            "artifact.ll",
            "artifact.json",
            "policy.json",
            "abi.json",
            "contracts.json",
            "release-table.json",
            "expected-report.json",
        )
        for filename in required:
            if not (directory / filename).is_file():
                fail(errors, directory / filename, "required bundle member is missing")
        if any(not (directory / filename).is_file() for filename in required):
            continue
        identity = read_json(errors, directory / "artifact.json")
        policy = read_json(errors, directory / "policy.json")
        abi = read_json(errors, directory / "abi.json")
        contracts = read_json(errors, directory / "contracts.json")
        release_table = read_json(errors, directory / "release-table.json")
        report = read_json(errors, directory / "expected-report.json")
        if any(value is None for value in (identity, policy, abi, contracts, release_table, report)):
            continue
        bc_hash = digest(directory / "artifact.bc")
        ll_hash = digest(directory / "artifact.ll")
        declared_bc_hash = identity.get("candidate_bitcode_sha256")
        declared_ll_hash = identity.get("derived_llvm_ir_sha256")
        if not isinstance(declared_bc_hash, str) or not SHA256.fullmatch(declared_bc_hash):
            fail(errors, directory / "artifact.json", "candidate bitcode digest is not SHA-256")
        elif declared_bc_hash != bc_hash:
            fail(errors, directory / "artifact.json", "candidate bitcode hash mismatch")
        if not isinstance(declared_ll_hash, str) or not SHA256.fullmatch(declared_ll_hash):
            fail(errors, directory / "artifact.json", "derived LLVM IR digest is not SHA-256")
        elif declared_ll_hash != ll_hash:
            fail(errors, directory / "artifact.json", "derived LLVM IR hash mismatch")
        if identity.get("schema_version") != "sps-artifact-candidate-v1":
            fail(errors, directory / "artifact.json", "unsupported candidate schema")
        if identity.get("artifact_role") != "checked-in-bitcode-candidate":
            fail(errors, directory / "artifact.json", "artifact role must remain an explicit candidate")
        if "canonical_bitcode_sha256" in identity or "NFConforms" in identity:
            fail(errors, directory / "artifact.json", "candidate envelope contains a forbidden conformance claim")
        profile = identity.get("rev4_profile")
        if not isinstance(profile, dict) or profile.get("required_llvm_version") != "22.1.8":
            fail(errors, directory / "artifact.json", "Rev4 LLVM 22.1.8 requirement is missing")
        elif (
            profile.get("not_authoritative") is not True
            or profile.get("promotion_requires_complete_rev4_replacement") is not True
            or not profile.get("missing")
        ):
            fail(errors, directory / "artifact.json", "candidate anti-overclaim profile is incomplete")
        producer = identity.get("producer")
        produced_by_required = (
            isinstance(profile, dict)
            and isinstance(producer, dict)
            and producer.get("llvm_version") == profile.get("required_llvm_version")
        )
        if isinstance(profile, dict) and profile.get("producer_matches_required_version") is not produced_by_required:
            fail(errors, directory / "artifact.json", "producer/profile version flag is inconsistent")
        source_name = identity.get("source_mlir")
        if not isinstance(source_name, str):
            fail(errors, directory / "artifact.json", "source_mlir is missing")
        else:
            source = (directory / source_name).resolve()
            try:
                source.relative_to(MLIR_DIR.resolve())
            except ValueError:
                fail(errors, directory / "artifact.json", "source_mlir must resolve inside mlir/")
            else:
                if not source.is_file() or identity.get("source_mlir_sha256") != digest(source):
                    fail(errors, directory / "artifact.json", "source MLIR hash mismatch")
        for sidecar_path, sidecar in (
            (directory / "policy.json", policy),
            (directory / "abi.json", abi),
            (directory / "contracts.json", contracts),
            (directory / "release-table.json", release_table),
            (directory / "expected-report.json", report),
        ):
            if sidecar.get("candidate_bitcode_sha256") != bc_hash:
                fail(errors, sidecar_path, "sidecar is not bound to artifact.bc")
        sidecar_hashes = identity.get("candidate_sidecar_sha256")
        if not isinstance(sidecar_hashes, dict):
            fail(errors, directory / "artifact.json", "candidate sidecar digests are missing")
        else:
            for filename in ("policy.json", "abi.json", "contracts.json", "release-table.json", "expected-report.json"):
                if sidecar_hashes.get(filename) != digest(directory / filename):
                    fail(errors, directory / "artifact.json", f"candidate digest mismatch for {filename}")
        if policy.get("schema_version") != "sps-fixture-policy-v0":
            fail(errors, directory / "policy.json", "unsupported fixture policy schema")
        if abi.get("schema_version") != "sps-fixture-abi-v0":
            fail(errors, directory / "abi.json", "unsupported fixture ABI schema")
        if contracts.get("schema_version") != "sps-fixture-contracts-v0":
            fail(errors, directory / "contracts.json", "unsupported fixture contracts schema")
        if release_table.get("schema_version") != "sps-fixture-release-table-v0":
            fail(errors, directory / "release-table.json", "unsupported fixture release-table schema")
        if report.get("schema_version") != "sps-fixture-oracle-v0":
            fail(errors, directory / "expected-report.json", "unsupported fixture oracle schema")
        if report.get("claimable_from_checked_in_pair") is not False:
            fail(errors, directory / "expected-report.json", "LLVM17 candidate cannot claim a Rev4 result")
        current = report.get("current_harness_status")
        if (
            not isinstance(current, dict)
            or current.get("kind") != "Pending"
            or not current.get("reasons")
        ):
            fail(errors, directory / "expected-report.json", "current harness status must remain Pending with reasons")
        oracle = report.get("oracle")
        if not isinstance(oracle, dict):
            fail(errors, directory / "expected-report.json", "oracle object is missing")
            continue
        entry = oracle.get("entry")
        if not isinstance(entry, str) or abi.get("entry") != entry:
            fail(errors, directory, "ABI and report must bind the same entry")
        if isinstance(entry, str):
            llvm_ir = (directory / "artifact.ll").read_text()
            entry_definitions = [
                function
                for function in llvm_functions(llvm_ir, entry)
                if function["kind"] == "define"
            ]
            if len(entry_definitions) != 1:
                fail(
                    errors,
                    directory / "artifact.ll",
                    f"ABI entry {entry!r} must be defined exactly once",
                )
            else:
                parameters = entry_definitions[0]["parameters"]
                arguments = abi.get("arguments")
                if not isinstance(arguments, list) or any(
                    not isinstance(argument, dict) for argument in arguments
                ):
                    fail(errors, directory / "abi.json", "ABI arguments must be objects")
                else:
                    indices = [argument.get("index") for argument in arguments]
                    if indices != list(range(len(arguments))):
                        fail(
                            errors,
                            directory / "abi.json",
                            "ABI argument indices must be contiguous and ordered",
                        )
                    if len(arguments) != len(parameters):
                        fail(
                            errors,
                            directory / "abi.json",
                            "ABI argument count does not match the entry signature",
                        )
                    else:
                        for position, (argument, parameter) in enumerate(
                            zip(arguments, parameters)
                        ):
                            kind = argument.get("kind")
                            pointer_typed = parameter == "ptr"
                            if kind == "root" and not pointer_typed:
                                fail(
                                    errors,
                                    directory / "abi.json",
                                    f"ABI root argument {position} is not pointer-typed",
                                )
                            elif kind == "scalar" and pointer_typed:
                                fail(
                                    errors,
                                    directory / "abi.json",
                                    f"ABI scalar argument {position} is pointer-typed",
                                )

                release_entries = release_table.get("entries")
                mechanism_contracts = contracts.get("mechanism_contracts")
                if not isinstance(release_entries, list) or any(
                    not isinstance(release, dict) for release in release_entries
                ):
                    fail(
                        errors,
                        directory / "release-table.json",
                        "release entries must be objects",
                    )
                    release_entries = []
                if not isinstance(mechanism_contracts, list) or any(
                    not isinstance(contract, dict)
                    for contract in mechanism_contracts
                ):
                    fail(
                        errors,
                        directory / "contracts.json",
                        "mechanism contracts must be objects",
                    )
                    mechanism_contracts = []

                carrier_callees: set[str] = set()
                entry_body = str(entry_definitions[0]["body"])
                for release in release_entries:
                    carrier = release.get("carrier")
                    if not isinstance(carrier, dict):
                        fail(
                            errors,
                            directory / "release-table.json",
                            "release carrier must be an object",
                        )
                        continue
                    callee = carrier.get("callee")
                    ordinal = carrier.get("ordinal")
                    multiplicity = release.get("multiplicity")
                    if not isinstance(callee, str):
                        fail(
                            errors,
                            directory / "release-table.json",
                            "release carrier callee must be a symbol",
                        )
                        continue
                    carrier_callees.add(callee)
                    calls = re.findall(
                        rf"\bcall\s+[^@\n]*@{re.escape(callee)}\s*\(", entry_body
                    )
                    if not isinstance(multiplicity, int) or multiplicity != len(calls):
                        fail(
                            errors,
                            directory / "release-table.json",
                            f"carrier {callee!r} multiplicity does not match direct calls",
                        )
                    if (
                        not isinstance(ordinal, int)
                        or ordinal < 0
                        or ordinal >= len(calls)
                    ):
                        fail(
                            errors,
                            directory / "release-table.json",
                            f"carrier {callee!r} ordinal does not select a direct call",
                        )

                contract_callees: set[str] = set()
                for contract in mechanism_contracts:
                    callee = contract.get("callee")
                    if not isinstance(callee, str):
                        fail(
                            errors,
                            directory / "contracts.json",
                            "mechanism contract callee must be a symbol",
                        )
                        continue
                    contract_callees.add(callee)
                    signatures = llvm_functions(llvm_ir, callee)
                    if len(signatures) != 1:
                        fail(
                            errors,
                            directory / "contracts.json",
                            f"mechanism callee {callee!r} must have one LLVM signature",
                        )
                        continue
                    contract_abi = contract.get("abi")
                    if not isinstance(contract_abi, dict):
                        fail(
                            errors,
                            directory / "contracts.json",
                            f"mechanism callee {callee!r} is missing its ABI",
                        )
                        continue
                    if (
                        contract_abi.get("arguments") != signatures[0]["parameters"]
                        or contract_abi.get("result") != signatures[0]["result"]
                    ):
                        fail(
                            errors,
                            directory / "contracts.json",
                            f"mechanism callee {callee!r} ABI does not match LLVM",
                        )
                if carrier_callees != contract_callees:
                    fail(
                        errors,
                        directory / "contracts.json",
                        "release carriers and mechanism contracts must name the same callees",
                    )
        placements = policy.get("placement")
        if not isinstance(placements, list) or sum(
            isinstance(item, dict) and item.get("entry") == entry for item in placements
        ) != 1:
            fail(errors, directory / "policy.json", "entry must have exactly one placement")
        check_status_record(errors, directory / "expected-report.json", oracle, policy)
    errors.extend(check_conformance_matrix())
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "check",
        choices=("provenance", "annotations", "artifacts", "all", "update-manifest"),
        default="all",
        nargs="?",
    )
    args = parser.parse_args()
    if args.check == "update-manifest":
        write_shape_manifest()
        print(f"wrote {SHAPE_MANIFEST.relative_to(ROOT)}")
        return 0

    errors: list[str] = []
    if args.check in ("provenance", "all"):
        errors.extend(check_provenance())
    if args.check in ("annotations", "all"):
        errors.extend(check_annotations())
    if args.check in ("artifacts", "all"):
        errors.extend(check_artifacts())
    if errors:
        print("\n".join(f"error: {message}" for message in errors), file=sys.stderr)
        return 1
    print(f"{args.check} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
