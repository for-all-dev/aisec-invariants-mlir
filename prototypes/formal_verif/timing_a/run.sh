#!/usr/bin/env bash
# Layer A demo — drives the reusable `ctverify` package (../ctverify) on this
# corpus. Shows the coverage delta: mul/div-secret kernels are `secure` under
# default constant-time and `insecure` only with the layer-A features.
set -uo pipefail
eval "$(opam env)"
cd "$(dirname "$0")"
CC="${CC:-gcc}"                    # override: CC=clang bash run.sh
CTV=(uv run --project ../ctverify --quiet ctverify)
mkdir -p bin

CASES="${*:-a_ct_baseline a_div_public a_div_divisor a_div_dividend a_mul_operand}"
echo "compiler: $CC   (ctverify checkct: defaultCT vs layerA, at -O0)"
printf "%-16s | %-10s | %-10s\n" "kernel" "defaultCT" "layerA"
printf -- "-----------------+------------+-----------\n"
for fn in $CASES; do
  $CC -m32 -O0 -no-pie -static -fno-stack-protector harness.c cases.c \
      -DFUNC=$fn -o bin/${fn}_${CC}_O0 2>/dev/null
  d=$("${CTV[@]}" checkct "bin/${fn}_${CC}_O0" --cfg a.cfg --features ct     | awk '{print $1}')
  a=$("${CTV[@]}" checkct "bin/${fn}_${CC}_O0" --cfg a.cfg --features layerA | awk '{print $1}')
  printf "%-16s | %-10s | %-10s\n" "$fn" "$d" "$a"
done
