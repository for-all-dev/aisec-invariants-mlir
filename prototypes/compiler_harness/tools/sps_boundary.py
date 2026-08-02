#!/usr/bin/env python3
"""Resolve one case-local annotated C/C++ boundary and its SPS sidecars."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from source_boundary.build_extractor import BuildError, ensure_extractor
from source_boundary.cross_layer import CrossLayerError, validate as validate_cross_layer
from source_boundary.resolver import (
    DEFAULT_INCLUDE,
    DEFAULT_SCHEMAS,
    ROOT,
    BoundaryError,
    case_primary_source,
    describe,
    resolve,
)


def _path_tool(value: str, name: str) -> Path:
    candidate = shutil.which(value) or value
    path = Path(candidate).resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise BoundaryError(f"{name} is not executable: {value}")
    return path


def _inputs(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    explicit = (args.source, args.policy, args.abi)
    if args.case is not None:
        if any(item is not None for item in explicit):
            raise BoundaryError("--case cannot be combined with explicit input paths")
        case = args.case.resolve()
        abi = case / "abi.sps.yaml"
        return (
            case_primary_source(case, args.schemas.resolve()),
            case / "policy.sps.yaml",
            abi,
        )
    if any(item is None for item in explicit):
        raise BoundaryError("provide --source, --policy, and --abi together")
    return args.source, args.policy, args.abi


def _write_json(path: str | None, value: object) -> None:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path == "-":
        sys.stdout.write(rendered)
    elif path is not None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        temporary.write_text(rendered, encoding="utf-8")
        os.replace(temporary, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--support-source", action="append", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--abi", type=Path)
    parser.add_argument("--mlir", type=Path)
    parser.add_argument("--candidate-policy", type=Path)
    parser.add_argument("--candidate-release-table", type=Path)
    parser.add_argument("--report", default="-")
    parser.add_argument("--resolved")
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--extractor", type=Path)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--llvm-config", default="llvm-config")
    parser.add_argument("--cxx")
    parser.add_argument("--annotations-include", type=Path, default=DEFAULT_INCLUDE)
    parser.add_argument("--schemas", type=Path, default=DEFAULT_SCHEMAS)
    args = parser.parse_args()
    try:
        source, policy, abi = _inputs(args)
        clang = _path_tool(args.clang, "clang")
        if args.extractor is not None:
            extractor = _path_tool(str(args.extractor), "SPS AST extractor")
        else:
            llvm_config = _path_tool(args.llvm_config, "llvm-config")
            build_root = Path(
                os.environ.get("LIT_BUILD_ROOT", ROOT / "build" / "source-boundary")
            )
            extractor = ensure_extractor(
                build_root / "tools" / "sps-ast-extract",
                llvm_config=llvm_config,
                cxx=args.cxx,
            )
        resolved, report = resolve(
            source=source,
            support_sources=args.support_source,
            policy_path=policy,
            abi_path=abi,
            extractor=extractor,
            clang=clang,
            include=args.annotations_include.resolve(),
            schemas=args.schemas.resolve(),
        )
        cross_layer = (args.mlir, args.candidate_policy, args.candidate_release_table)
        if any(item is not None for item in cross_layer):
            if any(item is None for item in cross_layer):
                raise BoundaryError(
                    "--mlir, --candidate-policy, and --candidate-release-table must be provided together"
                )
            validate_cross_layer(
                source=source,
                policy_path=policy,
                abi_path=abi,
                mlir_path=args.mlir,
                candidate_policy_path=args.candidate_policy,
                candidate_release_path=args.candidate_release_table,
                resolved=resolved,
            )
            report["completedChecks"] = sorted(
                [*report["completedChecks"], "CrossLayerReferencesResolved"]
            )
        if args.describe:
            if args.report == "-":
                raise BoundaryError("--describe requires --report to name a file")
            sys.stdout.write(describe(resolved, report))
        _write_json(args.resolved, resolved)
        _write_json(args.report, report)
    except (BoundaryError, BuildError, CrossLayerError) as error:
        raise SystemExit(f"source boundary error: {error}") from error


if __name__ == "__main__":
    main()
