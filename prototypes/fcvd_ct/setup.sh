#!/usr/bin/env bash
# Set up the FCVD (xdsl-smt) checkout this prototype builds on.
#
# xdsl-smt ships no LICENSE file, so it is NOT vendored into this repo: it stays
# an external checkout. See ../../docs/research/fcvd-selfcomposition.agents.md §5.
set -euo pipefail

FCVD_DIR="${FCVD_DIR:-$HOME/third_party/xdsl-smt}"
FCVD_REV="${FCVD_REV:-dd30235}"

if [ ! -d "$FCVD_DIR" ]; then
  mkdir -p "$(dirname "$FCVD_DIR")"
  git clone https://github.com/opencompl/xdsl-smt.git "$FCVD_DIR"
fi

cd "$FCVD_DIR"
git checkout --quiet "$FCVD_REV"
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[dev]'

echo
echo "FCVD ready at $FCVD_DIR (rev $FCVD_REV)"
echo "Activate with: source $FCVD_DIR/.venv/bin/activate"
echo "Upstream test suite: lit tests/filecheck    # 171 pass / 6 fail / 5 xfail as of dd30235"
