#!/usr/bin/env bash
# Set up the FCVD (xdsl-smt) checkout this prototype builds on, then the venv.
#
# xdsl-smt ships no LICENSE file, so it is NOT vendored into this repo: it stays an
# external, gitignored checkout under third_party/ that uv installs as an editable
# path dependency. See ../../docs/research/fcvd-selfcomposition.agents.md §5.
# (A uv git dependency does not work: xdsl-smt has an ssh-only submodule.)
set -euo pipefail

cd "$(dirname "$0")"
FCVD_REV="${FCVD_REV:-dd30235009046929c7e8a17f4b2000e375296566}"

if [ ! -e third_party/xdsl-smt ]; then
  mkdir -p third_party
  git clone https://github.com/opencompl/xdsl-smt.git third_party/xdsl-smt
fi

git -C third_party/xdsl-smt checkout --quiet "$FCVD_REV"
uv sync

echo
echo "FCVD pinned at $FCVD_REV, environment ready."
echo "  uv run fcvd-ct-pdl patterns/shift_to_div.mlir --counterexample"
echo "  uv run verify-pdl  patterns/shift_to_div.mlir   # upstream's value check"
echo "  uv run pytest"
echo
echo "Upstream's own suite (171 pass / 6 fail / 5 xfail at this rev, failures are in"
echo "tensor-theory, superoptimize and xdsl-smt-run):"
echo "  (cd third_party/xdsl-smt && uv run --project ../.. lit tests/filecheck)"
