#!/usr/bin/env python3
"""Check that an NFv2 marker contributes no final-machine instruction bytes."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


SYMBOL = re.compile(r"^[0-9A-Fa-f]+ <([^>]+)>:$")
INSTRUCTION = re.compile(
    r"^\s*[0-9A-Fa-f]+:\s+((?:[0-9A-Fa-f]{2}(?:\s+|$))+)", re.MULTILINE
)
NAME = re.compile(r"^\s*Name: ([^ (]+)", re.MULTILINE)
SIZE = re.compile(r"^\s*Size: ([0-9]+)", re.MULTILINE)


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stderr}"
        )
    return completed.stdout


def _symbol_sizes(readobj: str) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for block in readobj.split("Symbol {")[1:]:
        block = block.split("}", 1)[0]
        name = NAME.search(block)
        size = SIZE.search(block)
        if name and size:
            sizes[name.group(1)] = int(size.group(1))
    return sizes


def _symbol_bytes(disassembly: str) -> dict[str, bytes]:
    result: dict[str, bytearray] = {}
    current: str | None = None
    for line in disassembly.splitlines():
        symbol = SYMBOL.match(line.strip())
        if symbol:
            current = symbol.group(1)
            result.setdefault(current, bytearray())
            continue
        if current is None:
            continue
        instruction = INSTRUCTION.match(line)
        if instruction:
            result[current].extend(
                int(byte, 16) for byte in instruction.group(1).split()
            )
    return {name: bytes(value) for name, value in result.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--objdump", required=True)
    parser.add_argument("--readobj", required=True)
    parser.add_argument("--object", required=True, type=Path)
    parser.add_argument("--marked", required=True)
    parser.add_argument("--control", required=True)
    arguments = parser.parse_args()
    try:
        readobj = _run(
            [arguments.readobj, "--symbols", "--relocations", str(arguments.object)]
        )
        if "llvm.sps.release" in readobj or "SPS_RELEASE" in readobj:
            raise ValueError("final object retains an SPS marker symbol or relocation")
        sizes = _symbol_sizes(readobj)
        disassembly = _run([arguments.objdump, "-d", str(arguments.object)])
        encoded = _symbol_bytes(disassembly)
        for name in (arguments.marked, arguments.control):
            if name not in sizes or sizes[name] <= 0:
                raise ValueError(f"missing nonempty function symbol: {name}")
            if name not in encoded or len(encoded[name]) < sizes[name]:
                raise ValueError(f"incomplete disassembly for function: {name}")
        marked = encoded[arguments.marked][: sizes[arguments.marked]]
        control = encoded[arguments.control][: sizes[arguments.control]]
        if marked != control:
            raise ValueError(
                "marked and control functions have different final instruction bytes: "
                f"{marked.hex()} != {control.hex()}"
            )
        print(
            f"verified zero-code SPS_RELEASE lowering: {arguments.marked} == "
            f"{arguments.control} ({len(marked)} bytes); no marker symbol or relocation"
        )
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
