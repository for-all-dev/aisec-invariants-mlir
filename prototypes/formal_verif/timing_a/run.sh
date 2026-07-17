#!/usr/bin/env bash
# Layer A — variable-latency (mul/div) constant-time checking with binsec.
#
# For each kernel prints three verdicts so the added coverage is visible:
#   defaultCT(-O0)  binsec checkct with control-flow + memory-access only
#   layerA(-O0)     + multiplication,dividend,divisor  (the layer-A features)
#   layerA(-O2)     same features after optimisation (compiler-effect check)
#
# The mul/div kernels are `secure` under defaultCT and only turn `insecure`
# under layerA: that DELTA is the point — default CT does not see timing leaks
# through variable-latency arithmetic.
set -uo pipefail
eval "$(opam env)"
cd "$(dirname "$0")"
CC="${CC:-gcc}"                     # override: CC=clang bash run.sh
DEFAULT="control-flow,memory-access"
LAYERA="control-flow,memory-access,multiplication,dividend,divisor"
mkdir -p bin

verdict() {  # $1 binary, $2 feature-set -> secure/insecure/unknown
  timeout 300 binsec -sse -checkct -checkct-features "$2" \
      -sse-script a.cfg -sse-timeout 240 "$1" 2>&1 \
    | grep -oiE "Program status is : (secure|insecure|unknown)" \
    | grep -oiE "(secure|insecure|unknown)$" | tail -1
}

CASES="${*:-a_ct_baseline a_div_public a_div_divisor a_div_dividend a_mul_operand}"
echo "compiler: $CC"
printf "%-16s | %-14s | %-12s | %-12s\n" "kernel" "defaultCT(-O0)" "layerA(-O0)" "layerA(-O2)"
printf -- "-----------------+----------------+--------------+-------------\n"
for fn in $CASES; do
  for opt in O0 O2; do
    $CC -m32 -$opt -no-pie -static -fno-stack-protector harness.c cases.c \
        -DFUNC=$fn -o bin/${fn}_${CC}_${opt} 2>/dev/null
  done
  d0=$(verdict "bin/${fn}_${CC}_O0" "$DEFAULT")
  a0=$(verdict "bin/${fn}_${CC}_O0" "$LAYERA")
  a2=$(verdict "bin/${fn}_${CC}_O2" "$LAYERA")
  printf "%-16s | %-14s | %-12s | %-12s\n" "$fn" "${d0:-?}" "${a0:-?}" "${a2:-?}"
done
