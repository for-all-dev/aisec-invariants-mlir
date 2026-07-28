#!/usr/bin/env bash
# P0 proof-of-concept: can the stock FCVD refinement checker serve as a
# constant-time checker if we fake self-composition by hand?
#
# Trick: put both traces in one function (secrets %s1, %s2, shared public %pub),
# return leak1 - leak2, and check it against a function returning 0.
#
# Answer: no. The refinement predicate propagates poison from the function
# arguments, so even the constant-time kernel comes back `sat`. The control
# (`const_zero.mlir`, same value but no argument dependence) is `unsat`, which
# pins the cause on poison rather than on our encoding. => the CT driver needs
# its own predicate: assume non-poison inputs, compare value components only.
set -euo pipefail

FCVD_DIR="${FCVD_DIR:-$HOME/third_party/xdsl-smt}"
# shellcheck disable=SC1091
source "$FCVD_DIR/.venv/bin/activate"
cd "$(dirname "$0")"

run() { echo "--- $1 (expect $2): $(xdsl-tv "$3" "$4" -opt | z3 -in)"; }

run "leaky kernel"        "sat"   spec_zero.mlir selfcomp_leaky.mlir
run "constant-time kernel" "unsat" spec_zero.mlir selfcomp_ct.mlir
run "poison control"      "unsat" spec_zero.mlir const_zero.mlir
run "identity sanity"     "unsat" spec_zero.mlir spec_zero.mlir
