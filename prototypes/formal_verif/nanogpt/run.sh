#!/usr/bin/env bash
# Weight-confidentiality verifier. For each kernel, build at -O0 (before) and
# -O2 (after), run `binsec -checkct`, and report whether the SECRET weights W
# leak through a branch or a memory-access address -- per compiler.
#   Usage:  bash run.sh            # gcc
#           CC=clang bash run.sh   # clang (the interesting arm)
set -uo pipefail
eval "$(opam env)" 2>/dev/null || true
cd "$(dirname "$0")"
HARNESS=harness.c
CC="${CC:-gcc}"
mkdir -p bin

verdict() {  # $1 binary -> "secure" / "insecure" / "unknown"
  timeout 300 binsec -sse -checkct -sse-script w.cfg -sse-timeout 240 "$1" 2>&1 \
    | grep -oiE "Program status is : (secure|insecure|unknown)" \
    | grep -oiE "(secure|insecure|unknown)$" | tail -1
}

KERNELS="${*:-mm_dense mm_sparse mm_codebook mm_codebook_ct}"
echo "compiler: $CC   secret = W[] (weights),  public = x[] (activations)"
printf "%-16s | %-9s | %-9s | %s\n" "kernel" "-O0" "-O2" "weight confidentiality"
printf -- "-----------------+-----------+-----------+----------------------------------\n"
for fn in $KERNELS; do
  for opt in O0 O2; do
    $CC -m32 -$opt -no-pie -static -fno-stack-protector "$HARNESS" cases.c \
        -DFUNC=$fn -o bin/${fn}_${CC}_${opt} 2>/dev/null
  done
  v0=$(verdict bin/${fn}_${CC}_O0); v2=$(verdict bin/${fn}_${CC}_O2)
  leak0=$([ "$v0" = insecure ] && echo Y || echo N)
  leak2=$([ "$v2" = insecure ] && echo Y || echo N)
  case "$leak0$leak2" in
    NN) q="oblivious (weights safe at O0 & O2)";;
    NY) q="*** COMPILER-INTRODUCED weight leak ***";;
    YY) q="leaks weights (authored; -O2 kept it)";;
    YN) q="leaks at O0; -O2 removed it";;
    *)  q="(build/verdict error)";;
  esac
  printf "%-16s | %-9s | %-9s | %s\n" "$fn" "${v0:-?}" "${v2:-?}" "$q"
done
