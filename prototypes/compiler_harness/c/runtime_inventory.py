#!/usr/bin/env python3
"""Select and validate the collision-free runtime fixture source inventory."""

from __future__ import annotations

import argparse
import difflib
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import checkpoint_model  # noqa: E402
import fixture_layout  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GROUPS = Path(__file__).resolve().with_name("runtime-source-groups.yaml")


class InventoryError(ValueError):
    pass


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InventoryError(f"{where}: expected an object")
    return value


def _exact_fields(value: dict[str, Any], expected: set[str], where: str) -> None:
    if set(value) != expected:
        raise InventoryError(
            f"{where}: expected fields {sorted(expected)}, got {sorted(value)}"
        )


def _relative_source(root: Path, value: Any, where: str) -> Path:
    if not isinstance(value, str) or not value:
        raise InventoryError(f"{where}: expected a nonempty path")
    try:
        path = checkpoint_model.resolve_root_path(root, value, where)
    except checkpoint_model.CheckpointError as error:
        raise InventoryError(str(error)) from error
    if path.suffix != ".c" or not path.is_file():
        raise InventoryError(f"{where}: must name an existing C source")
    return path


def load_groups(root: Path, manifest: Path) -> dict[str, tuple[Path, tuple[Path, ...]]]:
    unsupported = sorted(
        path
        for suffix in ("*.cc", "*.cpp", "*.cxx")
        for path in (root / "fixtures").glob(f"*/*/{suffix}")
        if path.is_file()
    )
    if unsupported:
        labels = ", ".join(str(path.relative_to(root)) for path in unsupported)
        raise InventoryError(
            "the runtime equivalence/coverage build currently supports C fixture "
            f"sources only; C++ sources require an explicit C++ link driver: {labels}"
        )
    try:
        value = checkpoint_model.strict_yaml_load(
            manifest.read_bytes(), source=str(manifest)
        )
    except (OSError, checkpoint_model.CheckpointError) as error:
        raise InventoryError(str(error)) from error
    top = _mapping(value, str(manifest))
    _exact_fields(top, {"groups"}, str(manifest))
    rows = _mapping(top["groups"], f"{manifest}.groups")
    groups: dict[str, tuple[Path, tuple[Path, ...]]] = {}
    claimed: dict[Path, str] = {}
    fixture_sources = {
        path.resolve() for path in fixture_layout.fixture_source_paths(root)
    }
    for identifier, raw in rows.items():
        if not isinstance(identifier, str) or not identifier:
            raise InventoryError(f"{manifest}.groups: group IDs must be nonempty strings")
        row = _mapping(raw, f"{manifest}.groups.{identifier}")
        _exact_fields(row, {"representative", "members"}, f"group {identifier}")
        raw_members = row["members"]
        if not isinstance(raw_members, list) or len(raw_members) < 2:
            raise InventoryError(f"group {identifier}: members must contain at least two paths")
        if raw_members != sorted(set(raw_members)):
            raise InventoryError(f"group {identifier}: members must be sorted and duplicate-free")
        members = tuple(
            _relative_source(root, item, f"group {identifier}.members[{index}]")
            for index, item in enumerate(raw_members)
        )
        representative = _relative_source(
            root, row["representative"], f"group {identifier}.representative"
        )
        if representative not in members:
            raise InventoryError(f"group {identifier}: representative is not a member")
        for source in members:
            if source not in fixture_sources:
                raise InventoryError(
                    f"group {identifier}: {source.relative_to(root)} is not fixture C evidence"
                )
            previous = claimed.get(source)
            if previous is not None:
                raise InventoryError(
                    f"{source.relative_to(root)} belongs to both {previous!r} and {identifier!r}"
                )
            claimed[source] = identifier
        groups[identifier] = (representative, members)
    return groups


def link_sources(
    root: Path, groups: dict[str, tuple[Path, tuple[Path, ...]]]
) -> list[Path]:
    omitted = {
        member.resolve()
        for representative, members in groups.values()
        for member in members
        if member != representative
    }
    return [
        source
        for source in fixture_layout.provenance_c_sources(root)
        if source.resolve() not in omitted
    ]


def _normal_llvm(source: Path, clang: Path, include: Path) -> str:
    command = [
        str(clang),
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
        "-fno-builtin",
        f"-I{include}",
        "-O0",
        "-Xclang",
        "-disable-O0-optnone",
        "-S",
        "-emit-llvm",
        str(source),
        "-o",
        "-",
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise InventoryError(
            f"normal LLVM compilation failed for {source}:\n{completed.stderr.rstrip()}"
        )
    lines = completed.stdout.splitlines()
    producer_nodes: set[str] = set()
    for line in lines:
        if line.startswith("!llvm.ident ="):
            producer_nodes.update(re.findall(r"!([0-9]+)", line))
    normalized: list[str] = []
    for line in lines:
        if line.startswith("; ModuleID =") or line.startswith("source_filename ="):
            continue
        if line.startswith("!llvm.ident ="):
            continue
        metadata = re.match(r"^!([0-9]+) =", line)
        if metadata is not None and metadata.group(1) in producer_nodes:
            continue
        normalized.append(line.rstrip())
    return "\n".join(normalized).strip() + "\n"


def check_normal_llvm(
    root: Path,
    groups: dict[str, tuple[Path, tuple[Path, ...]]],
    clang: Path,
    include: Path,
) -> None:
    for identifier, (representative, members) in groups.items():
        expected = _normal_llvm(representative, clang, include)
        for member in members:
            if member == representative:
                continue
            actual = _normal_llvm(member, clang, include)
            if actual == expected:
                continue
            difference = "\n".join(
                difflib.unified_diff(
                    expected.splitlines(),
                    actual.splitlines(),
                    fromfile=str(representative.relative_to(root)),
                    tofile=str(member.relative_to(root)),
                    lineterm="",
                    n=3,
                )
            )
            raise InventoryError(
                f"runtime source group {identifier!r} is not normal-LLVM-equal:\n{difference}"
            )


def _defined_external_symbols(llvm_nm: Path, object_path: Path) -> set[str]:
    completed = subprocess.run(
        [
            str(llvm_nm),
            "--defined-only",
            "--extern-only",
            "--format=just-symbols",
            str(object_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise InventoryError(
            f"cannot inspect {object_path}: {completed.stderr.rstrip()}"
        )
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def check_objects(
    root: Path,
    groups: dict[str, tuple[Path, tuple[Path, ...]]],
    object_root: Path,
    llvm_nm: Path,
) -> None:
    sources = fixture_layout.provenance_c_sources(root)
    by_symbol: dict[str, list[Path]] = defaultdict(list)
    for source in sources:
        relative = source.relative_to(root).with_suffix(".o")
        object_path = object_root / relative
        if not object_path.is_file():
            raise InventoryError(f"missing independently compiled object: {object_path}")
        for symbol in _defined_external_symbols(llvm_nm, object_path):
            by_symbol[symbol].append(source)

    member_group = {
        member.resolve(): identifier
        for identifier, (_, members) in groups.items()
        for member in members
    }
    errors: list[str] = []
    for symbol, owners in sorted(by_symbol.items()):
        if len(owners) < 2:
            continue
        identifiers = {member_group.get(owner.resolve()) for owner in owners}
        if len(identifiers) != 1 or None in identifiers:
            labels = ", ".join(str(owner.relative_to(root)) for owner in owners)
            errors.append(f"duplicate strong symbol {symbol!r} is not one declared group: {labels}")

    selected = link_sources(root, groups)
    selected_symbols: dict[str, Path] = {}
    for source in selected:
        relative = source.relative_to(root).with_suffix(".o")
        object_path = object_root / relative
        for symbol in _defined_external_symbols(llvm_nm, object_path):
            previous = selected_symbols.get(symbol)
            if previous is not None:
                errors.append(
                    f"runtime link still contains duplicate strong symbol {symbol!r}: "
                    f"{previous.relative_to(root)}, {source.relative_to(root)}"
                )
            else:
                selected_symbols[symbol] = source
    if errors:
        raise InventoryError("\n".join(errors))


def _display(path: Path, relative_to: Path | None) -> str:
    if relative_to is None:
        return str(path)
    return os.path.relpath(path, relative_to)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_GROUPS)
    parser.add_argument("--relative-to", type=Path)
    parser.add_argument("--list-link-c-sources", action="store_true")
    parser.add_argument("--check-normal-llvm", action="store_true")
    parser.add_argument("--check-objects", action="store_true")
    parser.add_argument("--clang", type=Path)
    parser.add_argument("--include", type=Path)
    parser.add_argument("--object-root", type=Path)
    parser.add_argument("--llvm-nm", type=Path)
    arguments = parser.parse_args()
    if not any(
        (
            arguments.list_link_c_sources,
            arguments.check_normal_llvm,
            arguments.check_objects,
        )
    ):
        parser.error("select an inventory action")
    try:
        root = arguments.root.resolve()
        groups = load_groups(root, arguments.manifest.resolve())
        if arguments.check_normal_llvm:
            if arguments.clang is None or arguments.include is None:
                parser.error("--check-normal-llvm requires --clang and --include")
            check_normal_llvm(
                root,
                groups,
                arguments.clang.resolve(),
                arguments.include.resolve(),
            )
            print("runtime duplicate normal-LLVM equivalence checks passed")
        if arguments.check_objects:
            if arguments.object_root is None or arguments.llvm_nm is None:
                parser.error("--check-objects requires --object-root and --llvm-nm")
            check_objects(
                root,
                groups,
                arguments.object_root.resolve(),
                arguments.llvm_nm.resolve(),
            )
            print("runtime link strong-symbol checks passed")
        if arguments.list_link_c_sources:
            relative_to = (
                arguments.relative_to.resolve()
                if arguments.relative_to is not None
                else None
            )
            for source in link_sources(root, groups):
                print(_display(source.resolve(), relative_to))
        return 0
    except InventoryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
