#!/usr/bin/env bash
# Layer D demo — the wall-clock net, as an information estimate.
#
# Compiles the corpus (cases.c) into the reusable measurement driver
# (../infoleak/csrc/driver.c) and drives the `infoleak` engine, which times each
# kernel on THIS CPU across two secret classes and estimates how many bits the
# timing leaks: I(secret; timing), debiased against a label-permutation null,
# plus the dudect/TVLA t-test.
#
# It also demonstrates the DENORMAL formal fix: since binsec cannot even decode
# FP (it returns `unknown`, not `secure`), the formal denormal layer is not a
# solver proof but a CONFIG proof — build under flush-to-zero and check it
# statically (`infoleak ftz`). We build the driver twice (normal + FTZ) and show
# the denormal channel present in one and gone in the other, agreeing with the
# static check.
#
# Unlike layers A/B this needs NO binsec and NO -m32: it measures the real
# native binary on the real silicon. It does need a C compiler and `uv`.
#
#   bash run.sh                 # gcc, default sample size
#   N=40000 bash run.sh         # more samples (tighter estimate)
set -uo pipefail
cd "$(dirname "$0")"
CC="${CC:-gcc}"
N="${N:-20000}"
WARMUP="${WARMUP:-2000}"
IL=(uv run --project ../infoleak --quiet infoleak)
mkdir -p bin

# -fno-fast-math is load-bearing for the normal build: the denormal channel only
# exists without flush-to-zero. The FTZ build adds -DINFOLEAK_FTZ so the driver
# enables FTZ/DAZ for the whole process (as an -ffast-math deployment would).
$CC -O2 -march=native -fno-fast-math -I ../infoleak/csrc \
    ../infoleak/csrc/driver.c cases.c -o bin/driver_${CC} || exit 1
$CC -O2 -march=native -fno-fast-math -DINFOLEAK_FTZ -I ../infoleak/csrc \
    ../infoleak/csrc/driver.c cases.c -o bin/driver_${CC}_ftz || exit 1

echo "compiler: $CC   samples: $N   (infoleak measure: I(secret;timing) in bits + dudect t)"
echo
echo "== layer D: bits leaked per kernel (normal build) =="
echo "   expected: d_ct_baseline silent | d_branch_earlyexit + d_denormal LEAK"
echo "             d_idiv_secret ~0 (Skylake idiv is constant-latency: binsec layerA"
echo "             flags it, but this CPU does not actually leak it — conservative)"
CASES="${*:-d_ct_baseline d_branch_earlyexit d_denormal d_idiv_secret}"
for fn in $CASES; do
  "${IL[@]}" measure "bin/driver_${CC}" "$fn" --n "$N" --warmup "$WARMUP"
done

echo
echo "== denormal formal fix: FTZ static check + D confirmation =="
printf "   ftz(normal build) : "; "${IL[@]}" ftz "bin/driver_${CC}"     || true
printf "   ftz(FTZ build)    : "; "${IL[@]}" ftz "bin/driver_${CC}_ftz" || true
echo "   d_denormal measured in each build:"
printf "     normal : "; "${IL[@]}" measure "bin/driver_${CC}"     d_denormal --n "$N" --warmup "$WARMUP" | sed 's/ — .*//'
printf "     FTZ    : "; "${IL[@]}" measure "bin/driver_${CC}_ftz" d_denormal --n "$N" --warmup "$WARMUP" | sed 's/ — .*//'
echo "   => FTZ closes the denormal channel; the static check predicts it, D confirms."
