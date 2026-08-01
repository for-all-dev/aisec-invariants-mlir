#!/usr/bin/env python3
"""Generate and verify non-claimable candidate bitcode fixture bundles.

The sidecars use ``SPS-Harness-*`` schemas.  They are partial preflight
matchers for the Rev-4 workflow, not canonical SPS interfaces or verifier
reports.  The ``*ResultMatcherV1`` tags correspond to the normative
``Constructed(PONFResultArtifactV1)`` and ``NotConstructedV1`` alternatives,
but deliberately omit identity-bound PONF, solver, and protected-evidence
fields.  A future conformance fixture must replace them with complete objects.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import sps_aggregation


ROOT = Path(__file__).resolve().parent.parent
SIDECARS = (
    "policy.json",
    "abi.json",
    "contracts.json",
    "release-table.json",
    "expected-report.json",
)
SPECS_PATH = ROOT / "artifacts" / "bundle-specs.json"
SPECS_FORMAT_ID = "SPS-Harness-Candidate-Bundle-Specs-v1"
ARTIFACT_FORMAT_ID = "SPS-Harness-Candidate-Artifact-v1"
SIDECAR_FORMAT_IDS = {
    "policy.json": "SPS-Harness-Candidate-Policy-v1",
    "abi.json": "SPS-Harness-Candidate-ABI-v1",
    "contracts.json": "SPS-Harness-Candidate-Contracts-v1",
    "release-table.json": "SPS-Harness-Candidate-Release-Table-v1",
    "expected-report.json": "SPS-Harness-Candidate-Expected-Run-v1",
}
BASE_V1_DEPLOYMENT_STATUS = {
    "tag": "Open",
    "args": [{"tag": "P4EvidenceProfileUnavailable"}],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tool(llvm_bin: Path, name: str) -> Path:
    path = llvm_bin / name
    if not path.is_file():
        raise SystemExit(f"missing required tool: {path}")
    return path


def version(path: Path) -> str:
    result = subprocess.run(
        [path, "--version"], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    return result.stdout.splitlines()[0].strip()


def write_json(path: Path, value: dict[str, object]) -> None:
    # Preserve declared field order so nested canonical SPS values retain
    # constructor ``tag`` before ``args``.  The surrounding object is a
    # harness matcher, but copied SPS values must still have their real shape.
    path.write_text(json.dumps(value, indent=2) + "\n")


def deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def expected_coalitions(policy: dict[str, object]) -> list[list[str]]:
    maxima = policy.get("maximal_adversary_coalitions")
    if not isinstance(maxima, list) or not maxima:
        raise ValueError("maximal_adversary_coalitions must be a nonempty array")
    coalitions: set[tuple[str, ...]] = set()
    for maximum in maxima:
        if not isinstance(maximum, list) or any(not isinstance(item, str) for item in maximum):
            raise ValueError("maximal adversary coalition must contain identifiers")
        if maximum != sorted(set(maximum)):
            raise ValueError("maximal adversary coalitions must be sorted and duplicate-free")
        for mask in range(1 << len(maximum)):
            coalitions.add(tuple(item for index, item in enumerate(maximum) if mask & (1 << index)))
    return [list(coalition) for coalition in sorted(coalitions, key=lambda item: (len(item), item))]


def nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(nested_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(nested_keys(item) for item in value))
    return set()


def validate_visibility_basis(
    failures: list[str],
    name: str,
    basis: object,
    principals: list[str],
    allowed_ids: set[str],
) -> None:
    required_keys = {"world_visible", "member_visible", "minimally_joint_visible"}
    if not isinstance(basis, dict) or set(basis) != required_keys:
        failures.append(f"{name} must be a complete VisibilityBasis-shaped object")
        return
    world = basis.get("world_visible")
    members = basis.get("member_visible")
    joint = basis.get("minimally_joint_visible")
    if not isinstance(world, list) or world != sorted(set(world)):
        failures.append(f"{name}.world_visible must be sorted and duplicate-free")
        world = []
    if not isinstance(members, dict) or list(members) != principals:
        failures.append(f"{name}.member_visible must be total in principal order")
        members = {}
    visible_ids = set(world)
    for principal, identifiers in members.items():
        if not isinstance(identifiers, list) or identifiers != sorted(set(identifiers)):
            failures.append(f"{name}.member_visible[{principal}] must be sorted and duplicate-free")
            continue
        visible_ids.update(identifiers)
    if not isinstance(joint, list):
        failures.append(f"{name}.minimally_joint_visible must be an array")
    elif joint:
        failures.append(f"{name}: joint visibility is not represented by this candidate harness schema")
    if not visible_ids <= allowed_ids:
        failures.append(f"{name} references undeclared identifiers")


def validate_spec(bundle: str, spec: dict[str, object]) -> None:
    failures: list[str] = []
    for filename, format_id in SIDECAR_FORMAT_IDS.items():
        key = filename.removesuffix(".json").replace("-", "_")
        value = spec.get(key)
        if not isinstance(value, dict) or value.get("format_id") != format_id:
            failures.append(f"{filename} must use {format_id}")

    policy = spec.get("policy")
    abi = spec.get("abi")
    report = spec.get("expected_report")
    if not isinstance(policy, dict) or not isinstance(abi, dict) or not isinstance(report, dict):
        raise SystemExit(f"{bundle}: " + "; ".join(failures or ["missing policy, ABI, or report"]))

    if {"confidentiality", "visibility"} & nested_keys(abi):
        failures.append("ABI must not author confidentiality or visibility labels")
    principals = policy.get("principals")
    if not isinstance(principals, list) or principals != sorted(set(principals)):
        failures.append("policy principals must be a sorted duplicate-free array")
        principals = []
    components = policy.get("components")
    if not isinstance(components, list) or components != sorted(set(components)):
        failures.append("policy components must be a sorted duplicate-free array")
        components = []
    arguments = abi.get("arguments")
    roles = policy.get("argument_roles")
    if not isinstance(arguments, list) or any(not isinstance(item, dict) for item in arguments):
        failures.append("ABI arguments must be an array of objects")
        arguments = []
    if not isinstance(roles, list) or any(not isinstance(item, dict) for item in roles):
        failures.append("policy argument_roles must be an array of objects")
        roles = []
    if [item.get("index") for item in arguments] != list(range(len(arguments))):
        failures.append("ABI argument indices must be contiguous and ordered")
    if [item.get("argument_index") for item in roles] != list(range(len(arguments))):
        failures.append("policy argument roles must cover ABI arguments in order")
    entry = abi.get("entry")
    if any(item.get("entry") != entry for item in roles):
        failures.append("policy argument roles must bind the ABI entry")
    allowed_roles = {
        "ComponentArgumentV1",
        "PointerRootArgumentV1",
        "PublicConfigurationArgumentV1",
    }
    component_basis = policy.get("component_visibility")
    world_components = (
        set(component_basis.get("world_visible", []))
        if isinstance(component_basis, dict)
        else set()
    )
    for index, (argument, role_record) in enumerate(zip(arguments, roles)):
        role = role_record.get("role")
        if not isinstance(role, dict) or role.get("tag") not in allowed_roles:
            failures.append(f"argument {index} has an invalid policy role")
            continue
        args = role.get("args")
        if not isinstance(args, list) or len(args) != 1 or not isinstance(args[0], str):
            failures.append(f"argument {index} role must carry one stable identifier")
            continue
        if role["tag"] == "PointerRootArgumentV1" and argument.get("kind") != "root":
            failures.append(f"argument {index} pointer-root role is not represented by an ABI root")
        if role["tag"] == "PointerRootArgumentV1" and argument.get("root_id") != args[0]:
            failures.append(f"argument {index} policy root and ABI root_id do not match")
        if role["tag"] != "PointerRootArgumentV1" and argument.get("kind") != "scalar":
            failures.append(f"argument {index} component role is not represented by an ABI scalar")
        if role["tag"] in {"ComponentArgumentV1", "PublicConfigurationArgumentV1"} and args[0] not in components:
            failures.append(f"argument {index} references an undeclared policy component")
        if role["tag"] == "PublicConfigurationArgumentV1" and args[0] not in world_components:
            failures.append(f"argument {index} public configuration is not world-visible in policy")

    root_ids = {
        item.get("root_id")
        for item in arguments
        if item.get("kind") == "root" and isinstance(item.get("root_id"), str)
    }
    if len(root_ids) != sum(item.get("kind") == "root" for item in arguments):
        failures.append("every ABI root must have a unique stable root_id")
    topology = abi.get("alias_topology")
    relations = topology.get("relations") if isinstance(topology, dict) else None
    if not isinstance(relations, list) or any(not isinstance(item, dict) for item in relations):
        failures.append("ABI alias topology relations must be objects")
    elif any(item.get("left") not in root_ids or item.get("right") not in root_ids for item in relations):
        failures.append("ABI alias topology must reference stable root_id values")
    initialized = abi.get("initialized_regions")
    if not isinstance(initialized, list) or any(not isinstance(item, dict) for item in initialized):
        failures.append("ABI initialized regions must be objects")
    elif any(item.get("root") not in root_ids for item in initialized):
        failures.append("ABI initialized regions must reference stable root_id values")

    output_ids = {
        item.get("output")
        for item in arguments
        if isinstance(item.get("output"), str)
    }
    validate_visibility_basis(
        failures,
        "component_visibility",
        policy.get("component_visibility"),
        principals,
        set(components),
    )
    validate_visibility_basis(
        failures,
        "output_visibility",
        policy.get("output_visibility"),
        principals,
        output_ids,
    )
    validate_visibility_basis(
        failures,
        "error_visibility",
        policy.get("error_visibility"),
        principals,
        set(),
    )

    if report.get("fixture_tier") != {"tag": "PreflightV1"}:
        failures.append("candidate report must declare the PreflightV1 tier")
    if report.get("claimable_from_checked_in_pair") is not False:
        failures.append("candidate report must remain non-claimable")
    current = report.get("current_harness_status")
    if not isinstance(current, dict) or current.get("tag") != "PendingV1" or not current.get("reasons"):
        failures.append("candidate report must remain PendingV1 with reasons")
    expected = report.get("expected")
    if not isinstance(expected, dict):
        failures.append("expected report matcher is missing")
        expected = {}
    if expected.get("entry") != entry:
        failures.append("expected report matcher and ABI must bind the same entry")
    if expected.get("expected_deployment_status") != BASE_V1_DEPLOYMENT_STATUS:
        failures.append("base Rev-4 deployment status must be Open(P4EvidenceProfileUnavailable)")
    if expected.get("expected_policy_review_status") != {"tag": "Complete"}:
        failures.append("candidate policy-review matcher must be Complete")

    rows = expected.get("audit_all_expectations")
    if not isinstance(rows, list) or not rows:
        failures.append("audit_all_expectations must be a nonempty array")
        rows = []
    try:
        required_coalitions = expected_coalitions(policy)
    except ValueError as error:
        failures.append(str(error))
        required_coalitions = []
    row_coalitions = [row.get("coalition") for row in rows if isinstance(row, dict)]
    if sorted(row_coalitions, key=lambda item: (len(item), item)) != required_coalitions:
        failures.append("AuditAll matchers must cover the exact coalition closure")

    accepted_bad = False
    unavailable = False
    unknown_reasons: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            failures.append("AuditAll matcher row must be an object")
            continue
        outcome = row.get("query_outcome")
        replay = row.get("replay_expectation")
        if not isinstance(outcome, dict) or not isinstance(replay, dict):
            failures.append(f"coalition {row.get('coalition')}: outcome and replay matchers are required")
            continue
        outcome_tag = outcome.get("tag")
        replay_tag = replay.get("tag")
        if outcome_tag == "ConstructedResultMatcherV1":
            raw = outcome.get("raw_solver_result")
            disposition = outcome.get("query_disposition")
            disposition_tag = disposition.get("tag") if isinstance(disposition, dict) else None
            legal = {
                "SAT": "CandidateOnly",
                "UNSAT": "Discharged",
                "UNKNOWN": "Unknown",
            }
            if legal.get(raw) != disposition_tag:
                failures.append(f"coalition {row.get('coalition')}: illegal AuditAll raw-result/disposition pair")
            if raw == "SAT":
                if replay_tag != "AcceptedBadStateRequiredV1" or not replay.get("bad_state_class"):
                    failures.append(f"coalition {row.get('coalition')}: SAT candidate needs an accepted-bad replay matcher")
                else:
                    accepted_bad = True
            elif raw == "UNSAT" and replay_tag != "NotApplicableV1":
                failures.append(f"coalition {row.get('coalition')}: discharged AuditAll must not expect replay")
            elif raw == "UNKNOWN":
                unavailable = True
                if disposition_tag == "Unknown":
                    args = disposition.get("args")
                    if isinstance(args, list) and len(args) == 1 and isinstance(args[0], dict):
                        if isinstance(args[0].get("reasonClassId"), str):
                            unknown_reasons.add(args[0]["reasonClassId"])
        elif outcome_tag == "NotConstructedResultMatcherV1":
            reason = outcome.get("reason")
            if not isinstance(reason, dict) or set(reason) != {"reasonClassId"}:
                failures.append(f"coalition {row.get('coalition')}: not-constructed matcher needs a canonical reason")
            if replay_tag != "NotAvailableV1" or replay.get("reason") != reason:
                failures.append(f"coalition {row.get('coalition')}: unavailable replay reason must match query construction")
            unavailable = True
            if isinstance(reason, dict) and isinstance(reason.get("reasonClassId"), str):
                unknown_reasons.add(reason["reasonClassId"])
        else:
            failures.append(f"coalition {row.get('coalition')}: invalid query-outcome matcher tag")

    model = expected.get("expected_model_status")
    if not isinstance(model, dict):
        failures.append("expected_model_status matcher is missing")
    elif accepted_bad:
        if model != {
            "tag": "Counterexample",
            "receipt_matcher": {"tag": "FreshProtectedReceiptMatcherV1"},
        }:
            failures.append("accepted bad replay requires a fresh-receipt Counterexample matcher")
    elif unavailable:
        # spec:4192-4196 collapses two or more DISTINCT open reasons to
        # Unknown(OpenModelObligations); keeping only the last row's reason
        # silently demanded a narrower tag. Shared rule: tools/sps_aggregation.py.
        if not unknown_reasons:
            failures.append("unavailable AuditAll requires the matching canonical Unknown reason")
        else:
            required_model = sps_aggregation.expected_model_status(
                accepted_bad_replay=False, blockers=unknown_reasons
            )
            if model != required_model:
                failures.append(
                    "unavailable AuditAll must aggregate to "
                    f"{sps_aggregation.describe(unknown_reasons)}"
                )
    elif model != {"tag": "Proved"}:
        failures.append("fully discharged AuditAll rows require a Proved tag matcher")

    if failures:
        raise SystemExit(f"{bundle}: " + "; ".join(failures))


def load_specs() -> dict[str, object]:
    value = json.loads(SPECS_PATH.read_text())
    if value.get("format_id") != SPECS_FORMAT_ID:
        raise SystemExit(f"unsupported bundle specs: {SPECS_PATH}")
    authority = value.get("catalog_authority")
    if authority != {"claimable": False, "tag": "CandidatePreflightCatalogV1"}:
        raise SystemExit("bundle-specs catalog must remain explicitly non-claimable")
    defaults = value.get("defaults")
    bundles = value.get("bundles")
    if not isinstance(defaults, dict):
        raise SystemExit("bundle-specs defaults must be an object")
    if not isinstance(bundles, dict) or not bundles:
        raise SystemExit("bundle-specs must contain a nonempty candidate inventory")
    merged = {name: deep_merge(defaults, spec) for name, spec in bundles.items()}
    for name, spec in merged.items():
        validate_spec(name, spec)
    return merged


def source_from_identity(bundle: str, directory: Path) -> Path:
    identity_path = directory / "artifact.json"
    if not identity_path.is_file():
        raise SystemExit(f"{bundle}: missing artifact.json source binding")
    identity = json.loads(identity_path.read_text())
    source_name = identity.get("source_mlir")
    if not isinstance(source_name, str):
        raise SystemExit(f"{bundle}: source_mlir is missing")
    source = (directory / source_name).resolve()
    try:
        source.relative_to((ROOT / "mlir").resolve())
    except ValueError as error:
        raise SystemExit(f"{bundle}: source_mlir must resolve inside mlir/") from error
    if not source.is_file() or not (source.parent / "snapshot.yaml").is_file():
        raise SystemExit(f"{bundle}: source_mlir must name a human-readable fixture")
    return source


def write_bound_sidecars(directory: Path, spec: dict[str, object], artifact_hash: str) -> None:
    for name in SIDECARS:
        key = name.removesuffix(".json").replace("-", "_")
        value = copy.deepcopy(spec[key])
        value["candidate_bitcode_sha256"] = artifact_hash
        write_json(directory / name, value)


def generate(llvm_bin: Path) -> None:
    translate = tool(llvm_bin, "mlir-translate")
    llvm_as = tool(llvm_bin, "llvm-as")
    llvm_dis = tool(llvm_bin, "llvm-dis")
    llvm_config = tool(llvm_bin, "llvm-config")
    llvm_version = subprocess.run(
        [llvm_config, "--version"], check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()
    producer = {
        "llvm_version": llvm_version,
        "mlir_translate": version(translate),
        "llvm_as": version(llvm_as),
        "llvm_dis": version(llvm_dis),
        "tool_sha256": {
            "mlir-translate": sha256(translate),
            "llvm-as": sha256(llvm_as),
            "llvm-dis": sha256(llvm_dis),
            "llvm-config": sha256(llvm_config),
        },
    }
    specs = load_specs()

    for bundle in sorted(specs):
        directory = ROOT / "artifacts" / bundle
        source = source_from_identity(bundle, directory)
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            translated = temporary_path / "translated.ll"
            bitcode = temporary_path / "artifact.bc"
            subprocess.run(
                [translate, "--mlir-to-llvmir", source, "-o", translated], check=True
            )
            subprocess.run([llvm_as, translated, "-o", bitcode], check=True)
            (directory / "artifact.bc").write_bytes(bitcode.read_bytes())
        subprocess.run(
            [llvm_dis, "artifact.bc", "-o", "artifact.ll"], cwd=directory, check=True
        )
        artifact_hash = sha256(directory / "artifact.bc")
        write_bound_sidecars(directory, specs[bundle], artifact_hash)
        identity = {
            "format_id": ARTIFACT_FORMAT_ID,
            "artifact_role": "checked-in-bitcode-candidate",
            "fixture_tier": {"tag": "PreflightV1"},
            "claimable": False,
            "candidate_bitcode_sha256": artifact_hash,
            "derived_llvm_ir_sha256": sha256(directory / "artifact.ll"),
            "candidate_sidecar_sha256": {
                name: sha256(directory / name) for name in SIDECARS
            },
            "source_mlir": f"../../{source.relative_to(ROOT).as_posix()}",
            "source_mlir_sha256": sha256(source),
            "producer": producer,
            "rev4_profile": {
                "required_llvm_version": "22.1.8",
                "producer_matches_required_version": llvm_version == "22.1.8",
                "not_authoritative": True,
                "promotion_requires_complete_rev4_replacement": True,
                "missing": [
                    "llvm-22.1.8-pinned-freeze-pipeline",
                    "complete-artifact-identity",
                    "canonical-rev4-interfaces",
                    "normal-form-audit-and-fresh-reparse",
                    "whole-entry-product-and-exact-replay",
                ],
            },
        }
        write_json(directory / "artifact.json", identity)
        print(f"generated {bundle}: {artifact_hash}")


def check(llvm_bin: Path) -> None:
    mlir_translate = tool(llvm_bin, "mlir-translate")
    llvm_as = tool(llvm_bin, "llvm-as")
    llvm_dis = tool(llvm_bin, "llvm-dis")
    llvm_config = tool(llvm_bin, "llvm-config")
    llvm_version = subprocess.run(
        [llvm_config, "--version"], check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()
    check_tool_hashes = {
        "mlir-translate": sha256(tool(llvm_bin, "mlir-translate")),
        "llvm-as": sha256(llvm_as),
        "llvm-dis": sha256(llvm_dis),
        "llvm-config": sha256(llvm_config),
    }
    specs = load_specs()
    failures: list[str] = []
    for bundle in sorted(specs):
        directory = ROOT / "artifacts" / bundle
        identity_path = directory / "artifact.json"
        if not identity_path.is_file():
            failures.append(f"{bundle}: missing artifact.json")
            continue
        identity = json.loads(identity_path.read_text())
        profile = identity.get("rev4_profile")
        if identity.get("format_id") != ARTIFACT_FORMAT_ID:
            failures.append(f"{bundle}: identity is not an explicit candidate schema")
        if identity.get("artifact_role") != "checked-in-bitcode-candidate":
            failures.append(f"{bundle}: artifact role is not candidate-only")
        if identity.get("fixture_tier") != {"tag": "PreflightV1"} or identity.get("claimable") is not False:
            failures.append(f"{bundle}: artifact candidate must remain non-claimable PreflightV1")
        if "canonical_bitcode_sha256" in identity or "NFConforms" in identity:
            failures.append(f"{bundle}: candidate identity contains a forbidden conformance claim")
        if (
            not isinstance(profile, dict)
            or profile.get("not_authoritative") is not True
            or profile.get("promotion_requires_complete_rev4_replacement") is not True
            or not profile.get("missing")
        ):
            failures.append(f"{bundle}: candidate anti-overclaim profile is incomplete")
        bc = directory / "artifact.bc"
        ll = directory / "artifact.ll"
        if not bc.is_file() or not ll.is_file():
            failures.append(f"{bundle}: missing artifact.bc or artifact.ll")
            continue
        if identity.get("candidate_bitcode_sha256") != sha256(bc):
            failures.append(f"{bundle}: bitcode hash mismatch")
        if identity.get("derived_llvm_ir_sha256") != sha256(ll):
            failures.append(f"{bundle}: llvm-ir hash mismatch")
        try:
            source = source_from_identity(bundle, directory)
        except SystemExit as error:
            failures.append(str(error))
            continue
        if identity.get("source_mlir_sha256") != sha256(source):
            failures.append(f"{bundle}: source MLIR hash mismatch; regenerate the pair")
        with tempfile.TemporaryDirectory() as temporary:
            translated = Path(temporary) / "source.ll"
            regenerated = Path(temporary) / "source.bc"
            try:
                subprocess.run(
                    [mlir_translate, "--mlir-to-llvmir", source, "-o", translated],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                subprocess.run(
                    [llvm_as, translated, "-o", regenerated],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError:
                failures.append(f"{bundle}: source MLIR does not lower to valid bitcode")
            else:
                if regenerated.read_bytes() != bc.read_bytes():
                    failures.append(
                        f"{bundle}: artifact.bc is not the exact lowering of source MLIR"
                    )
        try:
            rendered = subprocess.run(
                [llvm_dis, "artifact.bc", "-o", "-"],
                cwd=directory,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout
        except subprocess.CalledProcessError:
            failures.append(f"{bundle}: invalid LLVM bitcode")
            rendered = None
        if rendered is not None and rendered != ll.read_bytes():
            failures.append(f"{bundle}: artifact.ll is not the exact llvm-dis rendering")
        with tempfile.TemporaryDirectory() as temporary:
            reassembled = Path(temporary) / "artifact.bc"
            try:
                subprocess.run(
                    [llvm_as, ll, "-o", reassembled],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError:
                failures.append(f"{bundle}: invalid derived LLVM IR")
            else:
                if reassembled.read_bytes() != bc.read_bytes():
                    failures.append(
                        f"{bundle}: artifact.ll does not reassemble to exact artifact.bc bytes"
                    )
        producer = identity.get("producer")
        if not isinstance(producer, dict) or producer.get("llvm_version") != llvm_version:
            failures.append(
                f"{bundle}: check toolchain {llvm_version!r} differs from recorded producer"
            )
        elif producer.get("tool_sha256") != check_tool_hashes:
            failures.append(f"{bundle}: check tool binaries differ from recorded producer")
        artifact_hash = sha256(bc)
        for name in SIDECARS:
            if not (directory / name).is_file():
                failures.append(f"{bundle}: missing {name}")
                continue
            value = json.loads((directory / name).read_text())
            if value.get("format_id") != SIDECAR_FORMAT_IDS[name]:
                failures.append(f"{bundle}/{name}: unsupported harness sidecar format")
            if value.get("candidate_bitcode_sha256") != artifact_hash:
                failures.append(f"{bundle}/{name}: artifact hash binding mismatch")
            expected = copy.deepcopy(specs[bundle][name.removesuffix(".json").replace("-", "_")])
            value.pop("candidate_bitcode_sha256", None)
            if value != expected:
                failures.append(f"{bundle}/{name}: differs from bundle-specs.json")
            sidecar_hashes = identity.get("candidate_sidecar_sha256")
            if not isinstance(sidecar_hashes, dict) or sidecar_hashes.get(name) != sha256(directory / name):
                failures.append(f"{bundle}/{name}: candidate envelope digest mismatch")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"verified {len(specs)} exact .bc/.ll pairs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "check"))
    parser.add_argument("--llvm-bin", type=Path, default=Path("/opt/homebrew/opt/llvm/bin"))
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.llvm_bin.resolve())
    else:
        check(args.llvm_bin.resolve())


if __name__ == "__main__":
    main()
