#!/usr/bin/env python3
"""Parse and verify every checked-in compiler representation in the harness."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_PARTS = frozenset({".git", ".venv", "__pycache__", "build"})


def checked_in_files(suffix: str) -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob(f"*{suffix}")
        if not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
    )


def run(command: list[Path | str]) -> None:
    subprocess.run([str(item) for item in command], check=True)


def required_tool(llvm_bin: Path, name: str) -> Path:
    path = llvm_bin / name
    if not path.is_file():
        raise SystemExit(f"missing required tool: {path}")
    return path


def check(llvm_bin: Path) -> None:
    clang = required_tool(llvm_bin, "clang")
    llc = required_tool(llvm_bin, "llc")
    llvm_as = required_tool(llvm_bin, "llvm-as")
    llvm_dis = required_tool(llvm_bin, "llvm-dis")
    mlir_opt = required_tool(llvm_bin, "mlir-opt")
    mlir_translate = required_tool(llvm_bin, "mlir-translate")
    opt = required_tool(llvm_bin, "opt")

    c_sources = sorted((ROOT / "c").glob("*.c"))
    mlir_sources = sorted((ROOT / "mlir").glob("*.mlir"))
    llvm_sources = checked_in_files(".ll")
    bitcode_sources = checked_in_files(".bc")
    mir_sources = checked_in_files(".mir")

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)

        for index, source in enumerate(c_sources):
            llvm_ir = temporary / f"c-{index}.ll"
            bitcode = temporary / f"c-{index}.bc"
            imported_mlir = temporary / f"c-{index}.mlir"
            run(
                [
                    clang,
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Wpedantic",
                    "-Werror",
                    "-fno-builtin",
                    "-O2",
                    "-c",
                    "-emit-llvm",
                    source,
                    "-o",
                    bitcode,
                ]
            )
            run([opt, "-passes=verify", "-disable-output", bitcode])
            run([llvm_dis, bitcode, "-o", llvm_ir])
            if source.name == "launder_scan_fixed.c":
                imported = subprocess.run(
                    [
                        str(mlir_translate),
                        "--import-llvm",
                        str(llvm_ir),
                        "-o",
                        str(imported_mlir),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                diagnostic = imported.stdout.lower()
                refusal_markers = ("unhandled", "unsupported", "not supported")
                if (
                    imported.returncode == 0
                    or "asm" not in diagnostic
                    or not any(marker in diagnostic for marker in refusal_markers)
                ):
                    raise SystemExit(
                        "launder_scan_fixed.c no longer has the expected "
                        "inline-asm import refusal"
                    )
            else:
                run([mlir_translate, "--import-llvm", llvm_ir, "-o", imported_mlir])
                run([mlir_opt, "--verify-each", imported_mlir, "-o", "/dev/null"])

        for index, source in enumerate(mlir_sources):
            llvm_ir = temporary / f"mlir-{index}.ll"
            bitcode = temporary / f"mlir-{index}.bc"
            run([mlir_translate, "--mlir-to-llvmir", source, "-o", llvm_ir])
            run([llvm_as, llvm_ir, "-o", bitcode])
            run([opt, "-passes=verify", "-disable-output", bitcode])

        for index, source in enumerate(llvm_sources):
            bitcode = temporary / f"llvm-{index}.bc"
            run([llvm_as, source, "-o", bitcode])
            run([opt, "-passes=verify", "-disable-output", bitcode])

        for index, source in enumerate(bitcode_sources):
            reparsed = temporary / f"frozen-{index}.bc"
            run([opt, "-passes=verify", source, "-o", reparsed])
            if reparsed.read_bytes() != source.read_bytes():
                raise SystemExit(
                    f"{source.relative_to(ROOT)} is not a fresh opt writer fixpoint"
                )

        for source in mir_sources:
            run([llc, "-run-pass=none", source, "-o", "/dev/null"])

    print(f"verified C -> bitcode: {len(c_sources)}")
    print(
        "verified C -> LLVM -> MLIR: "
        f"{len(c_sources) - 1}; expected inline-asm refusals: 1"
    )
    print(f"verified MLIR -> LLVM -> bitcode: {len(mlir_sources)}")
    print(f"verified textual LLVM: {len(llvm_sources)}")
    print(f"verified frozen bitcode fresh-reparse fixpoints: {len(bitcode_sources)}")
    print(f"verified machine basic-block snapshots: {len(mir_sources)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--llvm-bin", type=Path, default=Path("/opt/homebrew/opt/llvm/bin")
    )
    args = parser.parse_args()
    check(args.llvm_bin.resolve())


if __name__ == "__main__":
    main()
