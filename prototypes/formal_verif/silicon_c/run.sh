#!/usr/bin/env bash
# Layer C demo — validate the A/B leakage contract against the real silicon.
#
# A/B decide, in a solver's MODEL, whether a program leaks under a contract
# ([ct] / [cache-line]). C asks whether the actual chip honours that model: it
# measures the same kernels on this CPU (via the layer-D information estimate)
# and compares the measured bits to what the contract ALLOWS. A "secure"
# contract allows 0 bits; any measured channel above the floor REFUTES it.
#
# This is the Revizor / Scam-V role (does the CPU leak beyond the contract?)
# expressed through the same bits-leaked estimate as layer D. It reuses layer D's
# corpus (../timing_d/cases.c) — one corpus, two lenses — exactly as layers A
# and B both run over ctverify.
#
# The `--contract-verdict` per kernel is the GROUND TRUTH from A/B:
#   d_ct_baseline       secure    (no secret-dependent op at all)
#   d_denormal          secure    (plain FP mul-acc: binsec/A/B see no leak)
#   d_branch_earlyexit  insecure  (control-flow leak: A/binsec catch it)
#
#   bash run.sh          # gcc
#   N=40000 bash run.sh  # more samples
set -uo pipefail
cd "$(dirname "$0")"
CC="${CC:-gcc}"
N="${N:-20000}"
WARMUP="${WARMUP:-2000}"
IL=(uv run --project ../infoleak --quiet infoleak)
mkdir -p bin

# Same build recipe as layer D (native, no fast-math); corpus reused from ../timing_d.
$CC -O2 -march=native -fno-fast-math -I ../infoleak/csrc \
    ../infoleak/csrc/driver.c ../timing_d/cases.c -o bin/driver_${CC} || exit 1
DRV="bin/driver_${CC}"

echo "compiler: $CC   samples: $N   (infoleak silicon: measured bits vs [ct] contract)"
echo

echo "== d_ct_baseline   (A/B: [ct] secure)   expect CONSISTENT =="
"${IL[@]}" silicon "$DRV" d_ct_baseline      --contract "[ct]" --contract-verdict secure   --n "$N" --warmup "$WARMUP"
echo
echo "== d_denormal      (A/B: [ct] secure)   expect CONTRACT-VIOLATED  <-- the headline =="
"${IL[@]}" silicon "$DRV" d_denormal         --contract "[ct]" --contract-verdict secure   --n "$N" --warmup "$WARMUP"
echo
echo "== d_branch_earlyexit (A: [ct] insecure) expect CONFIRMED =="
"${IL[@]}" silicon "$DRV" d_branch_earlyexit --contract "[ct]" --contract-verdict insecure --n "$N" --warmup "$WARMUP"
