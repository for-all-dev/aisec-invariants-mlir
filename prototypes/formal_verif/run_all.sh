#!/usr/bin/env bash
# In-container orchestrator: reproduce the whole formal_verif result set.
# Runs the 2x2 CT quadrant matrix for gcc AND clang, then the functional-
# equivalence track (positive + negative controls). This is the image CMD.
set -uo pipefail
cd "$(dirname "$0")"

rule() { printf '\n\033[1m==== %s ====\033[0m\n' "$*"; }

rule "QUADRANTS — gcc (before=-O0, after=-O2)"
CC=gcc bash quadrants/run.sh

rule "QUADRANTS — clang  (expect q_oblivious / q_intro* => 'ДОБАВИЛ')"
CC=clang bash quadrants/run.sh

rule "FUNCTIONAL EQUIVALENCE — positive control (expect EQUIVALENT)"
# clang O0 vs O2 of the constant-time select: meaning preserved even though
# clang breaks its constant-timeness (the orthogonality headline).
CC=clang bash equiv/run.sh

rule "FUNCTIONAL EQUIVALENCE — negative control (expect NOT EQUIVALENT)"
# fut_diff.c is a deliberately different function => DIFF reachable => cex.
CC=gcc bash equiv/run.sh fut_diff.c

rule "DONE"
