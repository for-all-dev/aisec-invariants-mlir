#!/usr/bin/env bash
# Everything this package can check, in one run: the kernels, the templates, the PDL
# rewrites, and the per-compiler coverage report. Verdicts are printed, not asserted --
# `uv run pytest` is what asserts them.
set -uo pipefail
cd "$(dirname "$0")"

banner() { printf '\n=== %s\n' "$1"; }

banner "kernels (self-composition, four obligations)"
for kernel in kernels/*.mlir kernels/*/*.mlir; do
  uv run fcvd-ct "$kernel" --unroll 8 | grep -E '^[^ ]|^  [a-z]+ +INSECURE|^  reason'
done

banner "lowering templates (structural specifications): both halves of the gate"
for template in templates/*.mlir templates/*/*.mlir; do
  uv run fcvd-ct-lowering "$template" --unroll 8 | head -3
done

banner "PDL rewrites"
for pattern in patterns/*.mlir; do
  uv run fcvd-ct-pdl "$pattern" | head -2
done

banner "compiler coverage"
uv run fcvd-ct-coverage --top 6
