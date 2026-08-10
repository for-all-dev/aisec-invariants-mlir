#!/usr/bin/env python3
"""Build the small Clang LibTooling SPS annotation extractor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path


SOURCE = Path(__file__).with_name("sps_ast_extract.cpp")


class BuildError(RuntimeError):
    pass


def _capture(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise BuildError(f"command failed: {' '.join(command)}: {detail.strip()}") from error
    return completed.stdout.strip()


def _llvm_flags(llvm_config: Path, kind: str) -> list[str]:
    return shlex.split(_capture([str(llvm_config), kind]))


def _compiler(llvm_config: Path, configured: str | None) -> Path:
    if configured:
        candidate = shutil.which(configured) or configured
        path = Path(candidate)
        if path.is_file():
            return path.resolve()
        raise BuildError(f"configured C++ compiler does not exist: {configured}")
    # On Darwin the system compiler uses the current SDK's libc++ headers;
    # this is more robust than an older Homebrew clang using its bundled copy.
    candidate = shutil.which("c++") or shutil.which("clang++")
    if candidate:
        return Path(candidate).resolve()
    adjacent = llvm_config.with_name("clang++")
    if adjacent.is_file():
        return adjacent.resolve()
    raise BuildError("no C++ compiler is available")


def _fingerprint(llvm_config: Path, compiler: Path) -> dict[str, str]:
    return {
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "llvm_config": str(llvm_config),
        "llvm_version": _capture([str(llvm_config), "--version"]),
        "compiler": str(compiler),
        "compiler_version": _capture([str(compiler), "--version"]).splitlines()[0],
    }


def ensure_extractor(
    output: Path,
    *,
    llvm_config: Path,
    cxx: str | None = None,
    force: bool = False,
) -> Path:
    output = output.resolve()
    llvm_config = llvm_config.resolve()
    if not llvm_config.is_file():
        raise BuildError(f"llvm-config does not exist: {llvm_config}")
    compiler = _compiler(llvm_config, cxx)
    fingerprint = _fingerprint(llvm_config, compiler)
    stamp = output.with_suffix(output.suffix + ".build.json")
    if not force and output.is_file() and os.access(output, os.X_OK) and stamp.is_file():
        try:
            if json.loads(stamp.read_text(encoding="utf-8")) == fingerprint:
                return output
        except (OSError, json.JSONDecodeError):
            pass

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        temporary_output = Path(temporary) / output.name
        command = [
            str(compiler),
            str(SOURCE),
            "-o",
            str(temporary_output),
            *(_llvm_flags(llvm_config, "--cxxflags")),
            *(_llvm_flags(llvm_config, "--ldflags")),
            "-lclang-cpp",
            *(_llvm_flags(llvm_config, "--libs")),
            *(_llvm_flags(llvm_config, "--system-libs")),
        ]
        try:
            completed = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            detail = getattr(error, "stderr", "") or str(error)
            raise BuildError(f"extractor build failed: {detail.strip()}") from error
        if completed.stdout.strip():
            raise BuildError("extractor build unexpectedly wrote to stdout")
        os.replace(temporary_output, output)
    output.chmod(0o755)
    temporary_stamp = stamp.with_name(f".{stamp.name}.{os.getpid()}.tmp")
    temporary_stamp.write_text(
        json.dumps(fingerprint, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_stamp, stamp)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--llvm-config", type=Path, default=Path("llvm-config"))
    parser.add_argument("--cxx")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    llvm_config = args.llvm_config
    if not llvm_config.is_absolute():
        resolved = shutil.which(str(llvm_config))
        if not resolved:
            raise SystemExit(f"llvm-config is not runnable: {llvm_config}")
        llvm_config = Path(resolved)
    try:
        output = ensure_extractor(
            args.output, llvm_config=llvm_config, cxx=args.cxx, force=args.force
        )
    except BuildError as error:
        raise SystemExit(str(error)) from error
    print(output)


if __name__ == "__main__":
    main()
