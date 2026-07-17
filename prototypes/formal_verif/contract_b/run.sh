#!/usr/bin/env bash
# Layer B demo — drives the reusable `ctverify` package (../ctverify) on this
# corpus. Per kernel it prints the [ct] (byte) verdict and the computed
# [cache-line] verdict; the layout (elem size x index count) is the source
# ground truth passed to `ctverify contract`.
set -uo pipefail
eval "$(opam env)"
cd "$(dirname "$0")"
CC="${CC:-gcc}"                    # override: CC=clang bash run.sh
CTV=(uv run --project ../ctverify --quiet ctverify)
mkdir -p bin

# kernel -> "elem_size index_count"  (from cases.c)
declare -A LAYOUT=(
  [b_dense]="0 1"
  [b_codebook_small]="4 8"
  [b_codebook_wide]="4 64"
  [b_embedding_row]="128 32"
)

CASES="${*:-b_dense b_codebook_small b_codebook_wide b_embedding_row}"
echo "compiler: $CC   (ctverify contract: [ct] byte-observer vs [cache-line] 64B)"
for fn in $CASES; do
  $CC -m32 -O0 -no-pie -static -fno-stack-protector harness.c cases.c \
      -DFUNC=$fn -o bin/${fn}_${CC}_O0 2>/dev/null
  read -r elem count <<<"${LAYOUT[$fn]}"
  printf "%-18s " "$fn"
  "${CTV[@]}" contract "bin/${fn}_${CC}_O0" --cfg b.cfg --elem "$elem" --count "$count"
done
