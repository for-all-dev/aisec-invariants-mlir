#!/usr/bin/env bash
# Layer B — leakage contract at cache-line granularity, on top of binsec.
#
# Per kernel: binsec `-checkct` (memory-access) gives the [ct] verdict and, when
# insecure, the leaking instruction address. contract.py then computes the
# [cache-line] verdict from the access layout (layout.tsv). The point is the
# SPLIT: kernels that are all `insecure` under [ct] separate under [cache-line]
# — a small one-line table is secure against a real cache observer, a wide table
# or an embedding-row gather is not.
set -uo pipefail
eval "$(opam env)"
cd "$(dirname "$0")"
CC="${CC:-gcc}"                 # override: CC=clang bash run.sh
mkdir -p bin

# Run binsec at BYTE granularity (default checkct features) -> [ct] verdict + leak addr.
ct_check() {  # $1 binary -> "<verdict>\t<leak_instr>"
  local out verdict instr
  out=$(timeout 300 binsec -sse -checkct -checkct-leak-info instr \
          -sse-script b.cfg -sse-timeout 240 "$1" 2>&1)
  verdict=$(grep -oiE "Program status is : (secure|insecure|unknown)" <<<"$out" \
            | grep -oiE "(secure|insecure|unknown)$" | tail -1)
  instr=$(grep -oiE "Instruction 0x[0-9a-f]+ has memory access leak" <<<"$out" \
          | grep -oiE "0x[0-9a-f]+" | head -1)
  printf "%s\t%s" "${verdict:-unknown}" "${instr:--}"
}

CASES="${*:-b_dense b_codebook_small b_codebook_wide b_embedding_row}"
echo "compiler: $CC   contract split: [ct] byte-observer vs [cache-line] 64B-observer"
printf "%-18s | %-9s | %-11s | %-11s | %s\n" "kernel" "[ct]" "[cache-line]" "leak@" "reason"
printf -- "-------------------+-----------+-------------+-------------+------------------------\n"
for fn in $CASES; do
  $CC -m32 -O0 -no-pie -static -fno-stack-protector harness.c cases.c \
      -DFUNC=$fn -o bin/${fn}_${CC}_O0 2>/dev/null
  IFS=$'\t' read -r verdict instr < <(ct_check "bin/${fn}_${CC}_O0")
  python3 contract.py "$fn" "$verdict" "$instr"
done
