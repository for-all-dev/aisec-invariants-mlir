#!/usr/bin/env bash
# Build each case at -O0 and -O2, run binsec -checkct, print verdict per (case,opt).
set -uo pipefail
eval "$(opam env)"
cd "$(dirname "$0")"
HARNESS=../calibration/harness.c
CC="${CC:-gcc}"          # override: CC=clang bash run.sh
mkdir -p bin

verdict() {  # $1 binary -> prints "secure"/"insecure"/"unknown"
  timeout 300 binsec -sse -checkct -sse-script q.cfg -sse-timeout 240 "$1" 2>&1 \
    | grep -oiE "Program status is : (secure|insecure|unknown)" | grep -oiE "(secure|insecure|unknown)$" | tail -1
}

CASES="${*:-q_oblivious q_removed q_kept_mem q_kept_cf q_intro1 q_intro2 q_intro3 q_intro4 q_intro5}"
echo "compiler: $CC   (before=-O0, after=-O2)"
printf "%-14s | %-9s | %-9s | %s\n" "case" "-O0" "-O2" "quadrant"
printf -- "---------------+-----------+-----------+--------------------------\n"
for fn in $CASES; do
  for opt in O0 O2; do
    $CC -m32 -$opt -no-pie -static -fno-stack-protector "$HARNESS" cases.c \
        -DFUNC=$fn -o bin/${fn}_${CC}_${opt} 2>/dev/null
  done
  eval "set -- bin/${fn}_${CC}_O0 bin/${fn}_${CC}_O2"; b0=$1; b2=$2
  v0=$(verdict "$b0"); v2=$(verdict "$b2")
  # classify
  leak0=$([ "$v0" = insecure ] && echo Y || echo N)
  leak2=$([ "$v2" = insecure ] && echo Y || echo N)
  case "$leak0$leak2" in
    NN) q="нет/нет (oblivious)";;
    NY) q="*** нет/ДОБАВИЛ (compiler-introduced) ***";;
    YY) q="есть/оставил (kept)";;
    YN) q="есть/убрал (removed)";;
  esac
  printf "%-14s | %-9s | %-9s | %s\n" "$fn" "$v0" "$v2" "$q"
done
