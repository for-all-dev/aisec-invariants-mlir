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

rule "nanoGPT WEIGHT-CONFIDENTIALITY — gcc  (secret = weights)"
CC=gcc bash nanogpt/run.sh

rule "nanoGPT WEIGHT-CONFIDENTIALITY — clang  (watch mm_codebook_ct for NY)"
CC=clang bash nanogpt/run.sh

rule "TIMING LAYER A — variable-latency CT (gcc)  [defaultCT vs layerA]"
CC=gcc bash timing_a/run.sh

rule "TIMING LAYER A — variable-latency CT (clang)"
CC=clang bash timing_a/run.sh

rule "LEAKAGE CONTRACT B — cache-line granularity (gcc)  [ct vs cache-line]"
CC=gcc bash contract_b/run.sh

rule "LEAKAGE CONTRACT B — cache-line granularity (clang)"
CC=clang bash contract_b/run.sh

# Layers C/D need NO binsec and NO -m32: they measure the native binary on the
# real silicon. They run even where the formal A/B tools are unavailable.
rule "TIMING LAYER D — wall-clock net as an information estimate (bits leaked)"
CC=gcc bash timing_d/run.sh

rule "TIMING LAYER C — validate the [ct] contract against real silicon"
CC=gcc bash silicon_c/run.sh

rule "ctverify UNIT TESTS  (parser + contract math; no binsec needed)"
( cd ctverify && uv run pytest )

rule "infoleak UNIT TESTS  (MI estimator calibration + layer-C logic; no CPU tuning needed)"
( cd infoleak && uv run pytest )

rule "DONE"
