#!/usr/bin/env bash
# Bounded functional-equivalence: is fut@-O0 == fut@-O2 for all inputs?
# DIFF unreachable => EQUIVALENT (proof, since fut is straight-line).
# Usage: CC=gcc|clang bash run.sh   [f2_source(default fut.c)]
set -uo pipefail; eval "$(opam env)"; cd "$(dirname "$0")"
CC="${CC:-gcc}"; F2SRC="${1:-fut.c}"; mkdir -p bin
$CC -m32 -O0 -c fut.c   -o bin/f0.o && objcopy --redefine-sym fut=f0 bin/f0.o
$CC -m32 -O2 -c "$F2SRC" -o bin/f2.o && objcopy --redefine-sym fut=f2 bin/f2.o
gcc -m32 -O0 -static -no-pie -fno-stack-protector harness.c bin/f0.o bin/f2.o -o bin/equiv
out=$(timeout 120 binsec -sse -sse-script equiv.cfg bin/equiv 2>&1)
if echo "$out" | grep -qi "reached address.*<DIFF>"; then
  echo "[$CC O0 vs O2 of $F2SRC] NOT EQUIVALENT — counterexample:"
  echo "$out" | grep -iE "gx|gy|gz|model|<-|=" | grep -ivE "queries|paths|info" | head
else
  echo "[$CC O0 vs O2 of $F2SRC] EQUIVALENT (DIFF provably unreachable)"
fi
