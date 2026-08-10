#!/usr/bin/env python3
"""Structural checks for SPS preflight fixtures and candidate bitcode bundles.

MLIR files in ``fixtures/`` are deliberately shape-only. They do not carry a
ModelStatus. Non-claimable future oracles live in case-local ``candidate/``
directories beside the readable fixture. They preserve the normative result
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import checkpoint_model  # noqa: E402  (shared Snapshot V3 contract)
import counterexample_pair  # noqa: E402  (non-claimable synthetic pair contract)
import fixture_layout  # noqa: E402  (shared fixture discovery)
import sps_aggregation  # noqa: E402  (shared normative aggregation rule)
import sps_interfaces  # noqa: E402  (SPS-owned wire registry)


ROOT = Path(__file__).resolve().parent.parent
SUPPORT_C_DIR = ROOT / "c"
FIXTURES_DIR = ROOT / "fixtures"
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

RETIRED_MLIR_HEADER_FIELDS = (
    "// case:",
    "// entry:",
    "// classification:",
    "// c source:",
    "// upstream GitHub source:",
    "// upstream revision:",
    "// secret:",
    "// public:",
    "// diagnostic focus:",
    "// fixture tier:",
    "// fixture scope:",
    "// normative target:",
)

LEGACY_RESULT_FIELDS = (
    "// expected outcome:",
    "// expected verdict:",
    "// observer/model:",
    "// reason id:",
    "// outstanding obligations:",
    "// result rows:",
    "// target tuple:",
    "// " + "l" + "1 disposition:",
)

LEGACY_BOUNDARY_FIELDS = (
    "// " + "evidence boundary:",
    "// " + "detection boundary:",
)

AUTHORITATIVE_RESULT_FIELDS = (
    "// model status:",
    "// ModelStatus:",
    "// deployment status:",
    "// DeploymentStatus:",
    "// policy review status:",
    "// product disposition:",
)

IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
MLIR_SYMBOL = re.compile(r"[A-Za-z_.$][A-Za-z0-9_.$-]*\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
LEGACY_LEVEL = re.compile(r"\bL[0-4]\b")
SNAPSHOT_OBSERVABLES = frozenset(
    {
        "address",
        "allocation-size",
        "control",
        "release-identity",
        "return",
        "timing",
        "transfer",
    }
)
INTERFACE_REGISTRY = sps_interfaces.load_default_registry()
PUBLIC_REASON_CLASS_IDS = frozenset(
    INTERFACE_REGISTRY.enum_values("PublicReasonClassesV2")
)
REQUIRED_CONFORMANCE_IDS = {
    *(f"NF-A{index:02d}" for index in range(1, 16)),
    *(f"NF-CM{index:02d}" for index in range(1, 13)),
}

ERROR_BLOCK = re.compile(
    r"(?m)^\s*// PREFLIGHT FINDING: .+\n"
    r"\s*// secret source: .+\n"
    r"\s*// observable effect: .+\n"
    r"\s*// reason: .+\n"
    r"\s*// preflight expectation: .+\n"
    r"\s*(?!//)(?:[%^}]|[a-zA-Z]).+"
)

REPAIR_BLOCK = re.compile(
    r"(?m)^\s*// PREFLIGHT CONTROL: .+\n"
    r"\s*// secret source: .+\n"
    r"\s*// (?:removed observable|safe effect): .+\n"
    r"\s*// reason: .+\n"
    r"\s*// preflight expectation: .+\n"
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
    return fixture_layout.provenance_c_sources(ROOT)


def check_provenance() -> list[str]:
    errors: list[str] = []
    mutable = re.compile(r"github\.com/[^/]+/[^/]+/(?:blob|tree)/(?:main|master)(?:/|$)")
    revision = re.compile(r"github\.com/[^/]+/[^/]+/(?:blob|tree)/([^/#?]+)(?:/|$)")

    unexpected_support_c = sorted(
        path for path in SUPPORT_C_DIR.glob("*.c") if path.name != "equivalence_driver.c"
    )
    for path in unexpected_support_c:
        fail(
            errors,
            path,
            "fixture C sources must live in a fixture case directory",
        )

    for path in c_sources():
        text = path.read_text()
        if LEGACY_LEVEL.search(text):
            fail(errors, path, "retired numbered-level vocabulary is forbidden; name the SPS responsibility")
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


def read_snapshot(
    errors: list[str], path: Path
) -> checkpoint_model.SnapshotV3 | None:
    try:
        return checkpoint_model.load_snapshot(path, ROOT)
    except (OSError, checkpoint_model.CheckpointError) as error:
        fail(errors, path, str(error))
        return None


def _entry_arguments(
    errors: list[str], path: Path, text: str, entry: str
) -> list[tuple[str, str]] | None:
    matches = list(
        re.finditer(rf"(?m)^\s*llvm\.func\s+@{re.escape(entry)}\s*\(", text)
    )
    if len(matches) != 1:
        fail(errors, path, f"entry {entry!r} must name exactly one llvm.func")
        return None
    opening = matches[0].end() - 1
    depth = 0
    quoted = False
    escaped = False
    closing = None
    for index in range(opening, len(text)):
        character = text[index]
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
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                closing = index
                break
    if closing is None:
        fail(errors, path, f"entry {entry!r} has an unterminated parameter list")
        return None
    arguments: list[tuple[str, str]] = []
    for position, argument in enumerate(
        split_llvm_arguments(text[opening + 1 : closing])
    ):
        match = re.match(r"\s*%([A-Za-z0-9_.$-]+)\s*:\s*(.+)\Z", argument, re.S)
        if not match:
            fail(errors, path, f"entry argument {position} is not a named LLVM argument")
            return None
        arguments.append((match.group(1), match.group(2).strip()))
    return arguments


def _argument_reference(
    errors: list[str],
    path: Path,
    item: object,
    arguments: list[tuple[str, str]],
    index_key: str,
    context: str,
) -> tuple[int, str] | None:
    if not isinstance(item, dict) or set(item) != {index_key, "name"}:
        fail(errors, path, f"{context} must contain exactly {index_key!r} and 'name'")
        return None
    index = item.get(index_key)
    name = item.get("name")
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        fail(errors, path, f"{context} argument index must be a nonnegative integer")
        return None
    if index >= len(arguments):
        fail(errors, path, f"{context} argument index {index} is out of range")
        return None
    if not isinstance(name, str) or name != arguments[index][0]:
        fail(
            errors,
            path,
            f"{context} name must match argument {index} ({arguments[index][0]!r})",
        )
        return None
    if index_key == "memory_at_arg" and "!llvm.ptr" not in arguments[index][1]:
        fail(errors, path, f"{context} argument {index} is not pointer-typed")
        return None
    return (index, name)


def snapshot_records() -> tuple[list[dict[str, object]], list[str]]:
    errors: list[str] = []
    records: list[dict[str, object]] = []
    snapshot_paths = sorted(FIXTURES_DIR.rglob("snapshot.yaml"))
    pair_paths = sorted(FIXTURES_DIR.rglob(counterexample_pair.FILENAME))
    mlir_paths = fixture_layout.fixture_mlir_paths(ROOT)
    authoring_owners: dict[Path, Path] = {}

    if not snapshot_paths:
        fail(errors, FIXTURES_DIR, "no snapshot.yaml fixtures were discovered")
    for pair_path in pair_paths:
        try:
            relative_parent = pair_path.parent.relative_to(FIXTURES_DIR)
        except ValueError:
            fail(errors, pair_path, "counterexample pair is outside fixtures/")
            continue
        if len(relative_parent.parts) != 2:
            fail(
                errors,
                pair_path,
                "counterexample pair must live at fixtures/<family>/<case>/",
            )
        if not (pair_path.parent / "snapshot.yaml").is_file():
            fail(errors, pair_path, "counterexample pair has no sibling snapshot.yaml")
    for mlir_path in mlir_paths:
        if not (mlir_path.parent / "snapshot.yaml").is_file():
            fail(errors, mlir_path, "fixture MLIR has no sibling snapshot.yaml")

    entries: dict[str, Path] = {}
    for snapshot_path in snapshot_paths:
        try:
            relative_parent = snapshot_path.parent.relative_to(FIXTURES_DIR)
        except ValueError:
            fail(errors, snapshot_path, "snapshot is outside fixtures/")
            continue
        if len(relative_parent.parts) != 2:
            fail(errors, snapshot_path, "snapshot must live at fixtures/<family>/<case>/")
        siblings = sorted(snapshot_path.parent.glob("*.mlir"))
        if len(siblings) != 1:
            fail(errors, snapshot_path, "snapshot must have exactly one sibling .mlir file")
            continue
        mlir_path = siblings[0]
        value = read_snapshot(errors, snapshot_path)
        if value is None:
            continue

        evidence = list(value.c_evidence)
        if evidence != sorted(set(evidence)):
            fail(errors, snapshot_path, "c_evidence must be sorted and duplicate-free")
        family = snapshot_path.parent.parent.resolve()
        resolved_evidence: list[Path] = []
        for position, evidence_name in enumerate(evidence):
            try:
                resolved = checkpoint_model.resolve_root_path(
                    ROOT, evidence_name, f"c_evidence[{position}]"
                )
            except checkpoint_model.CheckpointError as error:
                fail(errors, snapshot_path, str(error))
                continue
            try:
                resolved.relative_to(family)
            except ValueError:
                fail(
                    errors,
                    snapshot_path,
                    f"c_evidence[{position}] escapes its fixture family",
                )
                continue
            if resolved.suffix not in {".c", ".cc", ".cpp", ".cxx"}:
                fail(
                    errors,
                    snapshot_path,
                    f"c_evidence[{position}] must name a C/C++ source",
                )
            else:
                resolved_evidence.append(resolved)
        if len(resolved_evidence) != len(set(resolved_evidence)):
            fail(errors, snapshot_path, "c_evidence resolves to duplicate C files")

        policy_path = snapshot_path.parent / "policy.sps.yaml"
        abi_path = snapshot_path.parent / "abi.sps.yaml"
        contracts_path = snapshot_path.parent / "contracts.sps.yaml"
        pair: counterexample_pair.CounterexamplePair | None = None
        try:
            pair = counterexample_pair.load_fixture_pair(value)
        except counterexample_pair.CounterexamplePairError as error:
            fail(errors, snapshot_path, str(error))
        case_sources = sorted(
            path
            for suffix in ("*.c", "*.cc", "*.cpp", "*.cxx")
            for path in snapshot_path.parent.glob(suffix)
        )
        has_source_authoring = policy_path.exists() or abi_path.exists() or bool(case_sources)
        primary_source: Path | None = None
        if has_source_authoring:
            if not policy_path.is_file():
                fail(errors, snapshot_path, "source-annotated case requires policy.sps.yaml")
            if not abi_path.is_file():
                fail(errors, snapshot_path, "source-annotated case requires abi.sps.yaml")
            if not case_sources:
                fail(
                    errors,
                    snapshot_path,
                    "source-annotated case must own a sibling primary C/C++ source",
                )
            if abi_path.is_file():
                try:
                    abi_authoring = checkpoint_model.strict_yaml_load(
                        abi_path.read_bytes(), source=str(abi_path)
                    )
                    abi_source = (
                        abi_authoring.get("source")
                        if isinstance(abi_authoring, dict)
                        else None
                    )
                    if (
                        not isinstance(abi_source, str)
                        or not abi_source
                        or Path(abi_source).name != abi_source
                    ):
                        fail(errors, abi_path, "ABI source must be a sibling basename")
                    else:
                        candidate = snapshot_path.parent / abi_source
                        if candidate not in case_sources:
                            fail(
                                errors,
                                abi_path,
                                f"ABI primary source {abi_source!r} is not a sibling C/C++ source",
                            )
                        else:
                            primary_source = candidate.resolve()
                except (OSError, checkpoint_model.CheckpointError) as error:
                    fail(errors, abi_path, str(error))
            expected_evidence = [path.resolve() for path in case_sources]
            if resolved_evidence != expected_evidence:
                fail(
                    errors,
                    snapshot_path,
                    "source-annotated case c_evidence must name every sibling C/C++ source",
                )
            if primary_source is not None and primary_source not in resolved_evidence:
                fail(
                    errors,
                    snapshot_path,
                    "source-annotated case c_evidence omits its ABI primary source",
                )
            if contracts_path.exists() and (
                not contracts_path.is_file() or contracts_path.is_symlink()
            ):
                fail(
                    errors,
                    contracts_path,
                    "optional contract authoring sidecar must be a regular file",
                )
            for owned_path in [*case_sources, policy_path, abi_path, contracts_path]:
                if not owned_path.exists():
                    continue
                if owned_path.is_symlink():
                    fail(errors, owned_path, "case-owned authoring files must not be symlinks")
                    continue
                resolved = owned_path.resolve()
                previous_owner = authoring_owners.get(resolved)
                if previous_owner is not None and previous_owner != snapshot_path.parent:
                    fail(
                        errors,
                        owned_path,
                        "case-owned authoring file is shared with "
                        f"{previous_owner.relative_to(ROOT)}",
                    )
                else:
                    authoring_owners[resolved] = snapshot_path.parent

        entry = value.entry
        previous = entries.get(entry)
        if previous is not None:
            fail(errors, snapshot_path, f"entry duplicates {previous.relative_to(ROOT)}")
        else:
            entries[entry] = snapshot_path

        text = mlir_path.read_text()
        arguments = _entry_arguments(errors, mlir_path, text, entry)
        if arguments is None:
            continue

        secret = value.secret
        seen_secret: set[int] = set()
        for position, item in enumerate(secret):
            reference = _argument_reference(
                errors, snapshot_path, item, arguments, "arg", f"secret[{position}]"
            )
            if reference is not None and reference[0] in seen_secret:
                fail(errors, snapshot_path, f"secret argument {reference[0]} is duplicated")
            elif reference is not None:
                seen_secret.add(reference[0])

        public = value.public
        seen_public: set[tuple[str, object]] = set()
        for position, item in enumerate(public):
            reference: tuple[str, object] | None = None
            if isinstance(item, dict) and set(item) == {"arg", "name"}:
                parsed = _argument_reference(
                    errors, snapshot_path, item, arguments, "arg", f"public[{position}]"
                )
                if parsed is not None:
                    reference = ("arg", parsed[0])
            elif isinstance(item, dict) and set(item) == {"memory_at_arg", "name"}:
                parsed = _argument_reference(
                    errors,
                    snapshot_path,
                    item,
                    arguments,
                    "memory_at_arg",
                    f"public[{position}]",
                )
                if parsed is not None:
                    reference = ("memory_at_arg", parsed[0])
            elif isinstance(item, dict) and set(item) == {"observable"}:
                observable = item.get("observable")
                if observable not in SNAPSHOT_OBSERVABLES:
                    fail(errors, snapshot_path, f"public[{position}] has an unknown observable")
                else:
                    reference = ("observable", observable)
            else:
                fail(
                    errors,
                    snapshot_path,
                    f"public[{position}] must be an arg, memory_at_arg, or observable item",
                )
            if reference is not None and reference in seen_public:
                fail(errors, snapshot_path, f"public observation {reference!r} is duplicated")
            elif reference is not None:
                seen_public.add(reference)

        for field in RETIRED_MLIR_HEADER_FIELDS:
            if field_values(text, field):
                fail(errors, mlir_path, f"retired MLIR header field {field!r}; use snapshot.yaml")
        for field in LEGACY_RESULT_FIELDS:
            if field_values(text, field):
                fail(errors, mlir_path, f"legacy result field {field!r} is forbidden")
        for field in AUTHORITATIVE_RESULT_FIELDS:
            if field_values(text, field):
                fail(errors, mlir_path, f"preflight fixture forbids authoritative field {field!r}")
        if LEGACY_LEVEL.search(text):
            fail(errors, mlir_path, "retired numbered-level vocabulary is forbidden")
        if any(field in text for field in LEGACY_BOUNDARY_FIELDS):
            fail(errors, mlir_path, "legacy boundary metadata is forbidden")
        if "--verify-diagnostics" in text or "expected-error @" in text:
            fail(errors, mlir_path, "fixture contains an unimplemented semantic diagnostic oracle")
        if re.search(r"sps\.alias\s*=", text):
            fail(errors, mlir_path, "self-authoritative sps.alias is forbidden")
        if "sps.world_structural_size" in text:
            fail(errors, mlir_path, "self-authoritative world-structural binding is forbidden")
        if len(ERROR_BLOCK.findall(text)) != text.count("PREFLIGHT FINDING:"):
            fail(errors, mlir_path, "has an incomplete or non-adjacent preflight finding block")
        if len(REPAIR_BLOCK.findall(text)) != text.count("PREFLIGHT CONTROL:"):
            fail(errors, mlir_path, "has an incomplete or non-adjacent preflight control block")

        records.append(
            {
                "path": snapshot_path,
                "mlir": mlir_path,
                "entry": entry,
                "c_evidence": resolved_evidence,
                "secret": value.secret,
                "public": value.public,
                "allowed": value.allowed,
                "snapshot": value,
                "counterexample_pair": pair,
                "counterexample_pair_digest": (
                    pair.canonical_digest if pair is not None else None
                ),
                "pipelines": value.pipelines,
                "final": value.final,
            }
        )

    by_case = {record["path"].parent: record for record in records}
    for case_dir, bad in sorted(by_case.items(), key=lambda item: str(item[0])):
        case_name = case_dir.name
        if case_name == "bad":
            fixed_name = "fixed"
        elif case_name.endswith("-bad"):
            fixed_name = f"{case_name[:-4]}-fixed"
        else:
            continue
        fixed = by_case.get(case_dir.parent / fixed_name)
        if fixed is None:
            continue
        for field in ("secret", "public", "allowed"):
            if bad[field] != fixed[field]:
                fail(
                    errors,
                    fixed["path"],
                    f"paired bad/fixed {field} boundary differs from {bad['path'].relative_to(ROOT)}",
                )

    referenced_c = {
        path.resolve()
        for record in records
        for path in record.get("c_evidence", [])
        if isinstance(path, Path)
    }
    for source in fixture_layout.fixture_source_paths(ROOT):
        if source.resolve() not in referenced_c:
            fail(errors, source, "fixture C source is not referenced by any snapshot c_evidence")
    return records, errors


def check_snapshots() -> list[str]:
    _, errors = snapshot_records()
    errors.extend(checkpoint_model.validate_inventory(ROOT))
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


def nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(nested_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(nested_keys(item) for item in value))
    return set()


def exact_keys(
    errors: list[str],
    path: Path,
    value: dict[str, object],
    expected: set[str],
    context: str,
) -> bool:
    actual = set(value)
    if actual == expected:
        return True
    fail(
        errors,
        path,
        f"{context} fields must be exactly {sorted(expected)}; "
        f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}",
    )
    return False


def coalition_members(errors: list[str], path: Path, value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list) or any(not isinstance(member, str) for member in value):
        fail(errors, path, f"coalition must be an array of principal identifiers: {value!r}")
        return None
    members = tuple(value)
    if tuple(sorted(set(members))) != members or any(
        not IDENTIFIER.fullmatch(member) for member in members
    ):
        fail(errors, path, f"coalition must be sorted, duplicate-free, and canonical: {value!r}")
        return None
    return members


def reason_class_id(
    errors: list[str], path: Path, value: object, context: str
) -> str | None:
    if (
        not isinstance(value, dict)
        or set(value) != {"reasonClassId"}
        or not isinstance(value.get("reasonClassId"), str)
        or value.get("reasonClassId") not in PUBLIC_REASON_CLASS_IDS
    ):
        fail(errors, path, f"{context} must name one exact PublicReasonClassesV2 member")
        return None
    return str(value["reasonClassId"])


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


def check_expected_run(
    errors: list[str], path: Path, report: dict[str, object], policy: dict[str, object]
) -> str | None:
    exact_keys(
        errors,
        path,
        report,
        {
            "candidate_bitcode_sha256",
            "claimable_from_checked_in_pair",
            "current_harness_status",
            "expected",
            "fixture_tier",
            "format_id",
            "required_checker_feature",
        },
        "candidate expected-run record",
    )
    if report.get("format_id") != "SPS-Harness-Candidate-Expected-Run-v2":
        fail(errors, path, "unsupported candidate expected-run format")
    if report.get("fixture_tier") != {"tag": "CandidateOnly"}:
        fail(errors, path, "candidate expected-run fixture tier must be CandidateOnly")
    if report.get("claimable_from_checked_in_pair") is not False:
        fail(errors, path, "candidate pair cannot claim a Rev4 result")
    if report.get("required_checker_feature") != "sps-verifier":
        fail(errors, path, "candidate expected run must require the SPS verifier")

    current = report.get("current_harness_status")
    if (
        not isinstance(current, dict)
        or set(current) != {"tag", "reasons"}
        or current.get("tag") != "PendingV2"
        or not isinstance(current.get("reasons"), list)
        or not current.get("reasons")
        or any(not isinstance(reason, str) or not reason for reason in current["reasons"])
    ):
        fail(errors, path, "current harness status must be PendingV2 with stable reasons")

    expected = report.get("expected")
    if not isinstance(expected, dict):
        fail(errors, path, "expected run matcher is missing")
        return None
    exact_keys(
        errors,
        path,
        expected,
        {
            "audit_all_expectations",
            "entry",
            "expected_deployment_status",
            "expected_model_status",
            "expected_policy_review_status",
        },
        "expected run matcher",
    )

    rows = expected.get("audit_all_expectations")
    if not isinstance(rows, list) or not rows:
        fail(errors, path, "audit_all_expectations must be a nonempty array")
        rows = []
    seen: set[tuple[str, ...]] = set()
    ordered_coalitions: list[tuple[str, ...]] = []
    accepted_bad_state = False
    unavailable_reasons: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fail(errors, path, f"audit-all row {index} must be an object")
            continue
        exact_keys(
            errors,
            path,
            row,
            {"coalition", "query_outcome", "replay_expectation"},
            f"audit-all row {index}",
        )
        members = coalition_members(errors, path, row.get("coalition"))
        if members is not None:
            ordered_coalitions.append(members)
            if members in seen:
                fail(errors, path, f"duplicate coalition {list(members)!r}")
            seen.add(members)

        query = row.get("query_outcome")
        replay = row.get("replay_expectation")
        if not isinstance(query, dict):
            fail(errors, path, f"audit-all row {index} query_outcome must be an object")
            continue
        if not isinstance(replay, dict):
            fail(errors, path, f"audit-all row {index} replay_expectation must be an object")
            continue

        query_tag = query.get("tag")
        replay_tag = replay.get("tag")
        if query_tag == "ConstructedResultMatcherV2":
            exact_keys(
                errors,
                path,
                query,
                {"query_disposition", "raw_solver_result", "tag"},
                f"audit-all row {index} constructed result",
            )
            disposition = query.get("query_disposition")
            raw = query.get("raw_solver_result")
            if raw == "UNSAT":
                if disposition != {"tag": "Discharged"}:
                    fail(errors, path, f"audit-all row {index} UNSAT must be Discharged")
                if replay != {"tag": "NotApplicableV2"}:
                    fail(errors, path, f"audit-all row {index} UNSAT replay must be NotApplicableV2")
            elif raw == "SAT":
                if disposition != {"tag": "CandidateOnly"}:
                    fail(errors, path, f"audit-all row {index} SAT must remain CandidateOnly")
                exact_keys(
                    errors,
                    path,
                    replay,
                    {"bad_state_class", "tag"},
                    f"audit-all row {index} accepted replay matcher",
                )
                if replay_tag != "AcceptedBadStateRequiredV2" or not isinstance(
                    replay.get("bad_state_class"), str
                ) or not IDENTIFIER.fullmatch(str(replay.get("bad_state_class"))):
                    fail(errors, path, f"audit-all row {index} SAT requires a canonical accepted-bad-state matcher")
                else:
                    accepted_bad_state = True
            elif raw == "UNKNOWN":
                if not isinstance(disposition, dict):
                    fail(errors, path, f"audit-all row {index} UNKNOWN disposition must be an object")
                    disposition_reason = None
                else:
                    exact_keys(
                        errors,
                        path,
                        disposition,
                        {"args", "tag"},
                        f"audit-all row {index} Unknown disposition",
                    )
                    args = disposition.get("args")
                    disposition_reason = (
                        reason_class_id(errors, path, args[0], "query Unknown reason")
                        if disposition.get("tag") == "Unknown"
                        and isinstance(args, list)
                        and len(args) == 1
                        else None
                    )
                    if disposition_reason is None:
                        fail(errors, path, f"audit-all row {index} UNKNOWN needs one canonical reason")
                exact_keys(
                    errors,
                    path,
                    replay,
                    {"reason", "tag"},
                    f"audit-all row {index} unavailable replay",
                )
                replay_reason = reason_class_id(errors, path, replay.get("reason"), "replay reason")
                if replay_tag != "NotAvailableV2" or replay_reason != disposition_reason:
                    fail(errors, path, f"audit-all row {index} UNKNOWN query and replay reasons must agree")
                if disposition_reason is not None:
                    unavailable_reasons.add(disposition_reason)
            else:
                fail(errors, path, f"audit-all row {index} has unsupported raw solver result")
        elif query_tag == "NotConstructedResultMatcherV2":
            exact_keys(
                errors,
                path,
                query,
                {"reason", "tag"},
                f"audit-all row {index} not-constructed result",
            )
            query_reason = reason_class_id(errors, path, query.get("reason"), "query reason")
            exact_keys(
                errors,
                path,
                replay,
                {"reason", "tag"},
                f"audit-all row {index} unavailable replay",
            )
            replay_reason = reason_class_id(errors, path, replay.get("reason"), "replay reason")
            if replay_tag != "NotAvailableV2" or query_reason != replay_reason:
                fail(errors, path, f"audit-all row {index} not-constructed query and replay reasons must agree")
            if query_reason is not None:
                unavailable_reasons.add(query_reason)
        else:
            fail(errors, path, f"audit-all row {index} has an unsupported query-outcome tag")

    required_rows = expected_coalitions(errors, path, policy)
    if seen != required_rows:
        fail(
            errors,
            path,
            "audit-all rows are not the exact coalition downward closure; "
            f"missing={sorted(required_rows - seen)}, extra={sorted(seen - required_rows)}",
        )
    required_order = sorted(required_rows, key=lambda coalition: (len(coalition), coalition))
    if ordered_coalitions != required_order:
        fail(errors, path, "audit-all rows must follow the canonical coalition query order")

    model = expected.get("expected_model_status")
    if not isinstance(model, dict):
        fail(errors, path, "expected_model_status must be an object")
    else:
        tag = model.get("tag")
        aggregate = "Counterexample" if accepted_bad_state else "Unknown" if unavailable_reasons else "Proved"
        if tag != aggregate:
            fail(errors, path, f"expected_model_status must aggregate to {aggregate}")
        if tag == "Proved":
            exact_keys(errors, path, model, {"tag"}, "Proved matcher")
        elif tag == "Counterexample":
            exact_keys(errors, path, model, {"receipt_matcher", "tag"}, "Counterexample matcher")
            if model.get("receipt_matcher") != {"tag": "FreshProtectedReceiptMatcherV2"}:
                fail(errors, path, "Counterexample must match a fresh protected receipt, not expose a witness")
        elif tag == "Unknown":
            exact_keys(errors, path, model, {"args", "tag"}, "Unknown matcher")
            args = model.get("args")
            if isinstance(args, list):
                for value in args:
                    reason_class_id(errors, path, value, "Unknown reason")
            # spec:4192-4196 -- exactly one open blocker carries its own class;
            # two or more distinct classes collapse to OpenModelObligations,
            # which is never itself a row reason. A subset test against the row
            # reasons therefore rejected the mandated answer and admitted a
            # narrower one. Shared rule: tools/sps_aggregation.py.
            typed_blockers = sps_aggregation.proof_completion_blockers(
                unavailable_reasons
            )
            aggregation_input = sps_aggregation.make_aggregation_input(
                accepted_bad_replay=None,
                blockers=typed_blockers,
                all_required_gates_closed=False,
            )
            outcome = sps_aggregation.aggregate_model_result(aggregation_input)
            assert isinstance(outcome, sps_aggregation.CompletedAggregationV2)
            required_model = outcome.model_status
            if model != required_model:
                fail(
                    errors,
                    path,
                    "expected_model_status must aggregate to "
                    f"{sps_aggregation.describe(typed_blockers)}",
                )
        else:
            fail(errors, path, "unsupported expected_model_status tag")

    deployment = expected.get("expected_deployment_status")
    if deployment != {
        "tag": "Open",
        "args": [{"tag": "P4EvidenceProfileUnavailable"}],
    }:
        fail(errors, path, "checked-in candidate deployment must remain Open(P4EvidenceProfileUnavailable)")
    if expected.get("expected_policy_review_status") != {"tag": "Complete"}:
        fail(errors, path, "candidate policy-review matcher must be Complete")

    entry = expected.get("entry")
    if not isinstance(entry, str) or not entry:
        fail(errors, path, "expected run entry must be a nonempty symbol")
        return None
    return entry


def check_conformance_matrix() -> list[str]:
    errors: list[str] = []
    matrix = read_json(errors, CONFORMANCE_MATRIX)
    if matrix is None:
        return errors
    if matrix.get("schema_version") != "SPS-Harness-Rev4-Conformance-Matrix-v2":
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
    pending_ids = [
        case.get("id")
        for case in cases
        if isinstance(case, dict) and case.get("harness_status") == "pending"
    ]
    if pending_ids:
        fail(
            errors,
            CONFORMANCE_MATRIX,
            "the fixed 27-row Rev4 matrix must have no pending rows; "
            f"remaining={pending_ids}",
        )
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
    candidate_dirs = fixture_layout.candidate_dirs(ROOT)
    local_specs = fixture_layout.candidate_spec_paths(ROOT)
    legacy = ROOT / "artifacts"
    if legacy.exists():
        fail(errors, legacy, "legacy global artifacts/ is forbidden")
    if not candidate_dirs:
        fail(errors, FIXTURES_DIR, "no candidate bundles were discovered")

    expected_specs = {directory / "bundle-spec.json" for directory in candidate_dirs}
    for spec_path in local_specs:
        if spec_path not in expected_specs:
            fail(errors, spec_path, "bundle-spec.json must be a direct child of candidate/")

    bundle_ids: dict[str, Path] = {}

    for directory in candidate_dirs:
        location_error = fixture_layout.validate_candidate_location(directory, ROOT)
        if location_error:
            fail(errors, directory, location_error)
        definitions = sorted(directory.glob("bundle-spec*.json"))
        if definitions != [directory / "bundle-spec.json"]:
            fail(
                errors,
                directory,
                "candidate must contain exactly one bundle-spec.json; "
                f"found {[path.name for path in definitions]}",
            )
        required = (
            "bundle-spec.json",
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
        spec = read_json(errors, directory / "bundle-spec.json")
        identity = read_json(errors, directory / "artifact.json")
        policy = read_json(errors, directory / "policy.json")
        abi = read_json(errors, directory / "abi.json")
        contracts = read_json(errors, directory / "contracts.json")
        release_table = read_json(errors, directory / "release-table.json")
        report = read_json(errors, directory / "expected-report.json")
        if any(value is None for value in (spec, identity, policy, abi, contracts, release_table, report)):
            continue
        assert spec is not None
        spec_fields = {
            "format_id",
            "bundle_id",
            "catalog_authority",
            "policy",
            "abi",
            "contracts",
            "release_table",
            "expected_report",
        }
        exact_keys(errors, directory / "bundle-spec.json", spec, spec_fields, "candidate spec")
        if spec.get("format_id") != "SPS-Harness-Candidate-Bundle-Spec-v2":
            fail(errors, directory / "bundle-spec.json", "unsupported candidate bundle spec")
        if spec.get("catalog_authority") != {
            "tag": "CandidatePreflightCatalogV2",
            "claimable": False,
        }:
            fail(errors, directory / "bundle-spec.json", "candidate authority must remain non-claimable")
        bundle_id = spec.get("bundle_id")
        if not isinstance(bundle_id, str) or not IDENTIFIER.fullmatch(bundle_id):
            fail(errors, directory / "bundle-spec.json", "bundle_id must be lower-kebab")
        elif bundle_id in bundle_ids:
            fail(
                errors,
                directory / "bundle-spec.json",
                f"bundle_id duplicates {bundle_ids[bundle_id].relative_to(ROOT)}",
            )
        else:
            bundle_ids[bundle_id] = directory / "bundle-spec.json"
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
        if identity.get("format_id") != "SPS-Harness-Candidate-Artifact-v2":
            fail(errors, directory / "artifact.json", "unsupported candidate artifact format")
        if identity.get("artifact_role") != "checked-in-bitcode-candidate":
            fail(errors, directory / "artifact.json", "artifact role must remain an explicit candidate")
        if identity.get("fixture_tier") != {"tag": "CandidateOnly"}:
            fail(errors, directory / "artifact.json", "candidate artifact tier must be CandidateOnly")
        if identity.get("claimable") is not False:
            fail(errors, directory / "artifact.json", "candidate artifact must remain non-claimable")
        if "canonical_bitcode_sha256" in identity or "NFConforms" in identity:
            fail(errors, directory / "artifact.json", "candidate envelope contains a forbidden conformance claim")
        profile = identity.get("rev4_profile")
        if not isinstance(profile, dict) or profile.get("required_llvm_version") != "22.1.8":
            fail(errors, directory / "artifact.json", "Rev4 LLVM 22.1.8 requirement is missing")
        elif (
            profile.get("not_authoritative") is not True
            or profile.get("v2_materialization_requires_new_capture") is not True
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
            try:
                expected_source = fixture_layout.sole_case_mlir(directory.parent)
            except ValueError as error:
                fail(errors, directory / "artifact.json", str(error))
            else:
                expected_name = f"../{expected_source.name}"
                source = (directory / source_name).resolve()
                if source_name != expected_name or source != expected_source.resolve():
                    fail(
                        errors,
                        directory / "artifact.json",
                        f"source_mlir must bind the sole sibling MLIR as {expected_name!r}",
                    )
                source_capture_hash = identity.get("source_mlir_sha256")
                if (
                    not isinstance(source_capture_hash, str)
                    or not SHA256.fullmatch(source_capture_hash)
                ):
                    fail(
                        errors,
                        directory / "artifact.json",
                        "capture-time source MLIR digest is not SHA-256",
                    )
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
        expected_formats = (
            (directory / "policy.json", policy, "SPS-Harness-Candidate-Policy-v2"),
            (directory / "abi.json", abi, "SPS-Harness-Candidate-ABI-v2"),
            (
                directory / "contracts.json",
                contracts,
                "SPS-Harness-Candidate-Contracts-v2",
            ),
            (
                directory / "release-table.json",
                release_table,
                "SPS-Harness-Candidate-Release-Table-v2",
            ),
        )
        for sidecar_path, sidecar, expected_format in expected_formats:
            if sidecar.get("format_id") != expected_format:
                fail(errors, sidecar_path, f"unsupported candidate format; expected {expected_format}")
        forbidden_abi_authority = {"confidentiality", "visibility"} & nested_keys(abi)
        if forbidden_abi_authority:
            fail(
                errors,
                directory / "abi.json",
                "ABI must not author confidentiality or visibility labels; policy is authoritative",
            )

        entry = check_expected_run(errors, directory / "expected-report.json", report, policy)
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
    errors.extend(check_conformance_matrix())
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "check",
        choices=(
            "provenance",
            "snapshots",
            "checkpoints",
            "artifacts",
            "all",
            "list-fixtures",
        ),
        default="all",
        nargs="?",
    )
    args = parser.parse_args()
    if args.check == "list-fixtures":
        records, errors = snapshot_records()
        if errors:
            print("\n".join(f"error: {message}" for message in errors), file=sys.stderr)
            return 1
        for record in records:
            case = record["path"].parent.relative_to(FIXTURES_DIR)
            pipelines = record["pipelines"]
            final = record["final"]
            pipeline_summary = ",".join(
                f"{identifier}[{pipeline.kind}]"
                for identifier, pipeline in pipelines.items()
            )
            print(
                f"{case}: entry={record['entry']} "
                f"expected-model={final.status} "
                f"expected-deployment={final.deployment} "
                f"expected-policy={final.policy} "
                f"events={len(final.events)} "
                f"reference={final.reference or '-'} "
                f"pipelines={pipeline_summary}"
            )
        print(f"{len(records)} fixtures")
        return 0

    errors: list[str] = []
    if args.check in ("provenance", "all"):
        errors.extend(check_provenance())
    if args.check in ("snapshots", "all"):
        errors.extend(check_snapshots())
    if args.check == "checkpoints":
        errors.extend(checkpoint_model.validate_inventory(ROOT))
    if args.check in ("artifacts", "all"):
        errors.extend(check_artifacts())
    if errors:
        print("\n".join(f"error: {message}" for message in errors), file=sys.stderr)
        return 1
    print(f"{args.check} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
