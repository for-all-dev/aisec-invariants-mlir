#!/usr/bin/env python3
"""Compile the case-local Clangover caller and separate helper assemblies."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True, type=Path)
    parser.add_argument("--include", required=True, type=Path)
    parser.add_argument("--primary", required=True, type=Path)
    parser.add_argument("--helper", required=True, type=Path)
    parser.add_argument("--endpoint", required=True, type=Path)
    parser.add_argument("--helper-output", required=True, type=Path)
    arguments = parser.parse_args()
    common = [
        str(arguments.clang),
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-fno-builtin",
        f"-I{arguments.include}",
        "--target=x86_64-unknown-linux-gnu",
        "-Os",
        "-fno-vectorize",
        "-fno-slp-vectorize",
        "-S",
    ]
    arguments.endpoint.parent.mkdir(parents=True, exist_ok=True)
    arguments.helper_output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [*common, str(arguments.primary), "-o", str(arguments.endpoint)], check=True
    )
    subprocess.run(
        [*common, str(arguments.helper), "-o", str(arguments.helper_output)], check=True
    )


if __name__ == "__main__":
    main()
