#!/usr/bin/env python3
"""Generate and verify checked-in candidate ``artifact.bc``/derived ``artifact.ll`` pairs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BUNDLES = {
    "abi-alias-disjoint": "abi_alias_disjoint.control.mlir",
    "abi-alias-mayalias-overlap": "abi_alias_mayalias_overlap.bad.mlir",
    "abi-alias-missing-binding": "abi_alias_missing_binding.unknown.mlir",
    "alloca-size-high": "alloca_size_high_count.unknown.mlir",
    "alloca-size-public": "alloca_size_public.control.mlir",
    "audience-mismatch": "audience_mismatch.bad.mlir",
    "bound-exhausted-public": "bound_exhausted_loop.unknown.mlir",
    "bound-secret-trip-count": "bound_secret_trip_count.bad.mlir",
    "launder-scan": "launder_scan.model_proved.p4_open.mlir",
}
SIDECARS = (
    "policy.json",
    "abi.json",
    "contracts.json",
    "release-table.json",
    "expected-report.json",
)
SPECS_PATH = ROOT / "artifacts" / "bundle-specs.json"


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
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_specs() -> dict[str, object]:
    value = json.loads(SPECS_PATH.read_text())
    if value.get("schema_version") != "sps-bundle-specs-v1":
        raise SystemExit(f"unsupported bundle specs: {SPECS_PATH}")
    defaults = value.get("defaults")
    bundles = value.get("bundles")
    if not isinstance(defaults, dict):
        raise SystemExit("bundle-specs defaults must be an object")
    if not isinstance(bundles, dict) or set(bundles) != set(BUNDLES):
        raise SystemExit("bundle-specs inventory does not match generator inventory")
    return {name: deep_merge(defaults, spec) for name, spec in bundles.items()}


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

    for bundle, source_name in BUNDLES.items():
        directory = ROOT / "artifacts" / bundle
        source = ROOT / "mlir" / source_name
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
            "schema_version": "sps-artifact-candidate-v1",
            "artifact_role": "checked-in-bitcode-candidate",
            "candidate_bitcode_sha256": artifact_hash,
            "derived_llvm_ir_sha256": sha256(directory / "artifact.ll"),
            "candidate_sidecar_sha256": {
                name: sha256(directory / name) for name in SIDECARS
            },
            "source_mlir": f"../../mlir/{source_name}",
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
    for bundle, source_name in BUNDLES.items():
        directory = ROOT / "artifacts" / bundle
        identity_path = directory / "artifact.json"
        if not identity_path.is_file():
            failures.append(f"{bundle}: missing artifact.json")
            continue
        identity = json.loads(identity_path.read_text())
        profile = identity.get("rev4_profile")
        if identity.get("schema_version") != "sps-artifact-candidate-v1":
            failures.append(f"{bundle}: identity is not an explicit candidate schema")
        if identity.get("artifact_role") != "checked-in-bitcode-candidate":
            failures.append(f"{bundle}: artifact role is not candidate-only")
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
        source = ROOT / "mlir" / source_name
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
    print(f"verified {len(BUNDLES)} exact .bc/.ll pairs")


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
