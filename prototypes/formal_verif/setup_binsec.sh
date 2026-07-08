#!/usr/bin/env bash
# Install BINSEC (incl. relational constant-time analysis) + Z3 via opam.
# Idempotent-ish; logs everything. Run: bash setup_binsec.sh
set -uo pipefail
LOG() { echo "[setup $(date +%H:%M:%S)] $*"; }

LOG "apt deps (opam, build tools, gcc-multilib for 32/64 bit targets)"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
     opam build-essential m4 pkg-config libgmp-dev gcc

LOG "opam init (sandboxing disabled: container-safe)"
if ! opam switch list 2>/dev/null | grep -q .; then
  opam init -y --disable-sandboxing --bare
  opam switch create default 5.1.1 || opam switch create default
fi
eval "$(opam env)"

LOG "opam install binsec + solvers"
opam install -y binsec z3 || { LOG "binsec/z3 opam install FAILED"; exit 1; }
# bitwuzla is binsec's preferred CT solver; optional, don't fail the run on it
opam install -y bitwuzla bitwuzla-cxx || LOG "bitwuzla optional install skipped/failed"

eval "$(opam env)"
LOG "verify: binsec version + look for constant-time / relational checker"
binsec --version 2>&1 | head -1
echo "--- checkct capability probe ---"
binsec --help 2>&1 | grep -iE "checkct|relational|constant|secret" || \
  echo "NOTE: no built-in checkct in --help; may need 'binsec -checkct' subcommand or the Binsec/Rel artifact"
LOG "DONE"
