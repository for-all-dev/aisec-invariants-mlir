#!/usr/bin/env bash
# Hunt the "compiler introduced" quadrant: sweep gcc+clang x O0..O3 over the
# q_intro* candidates. Print verdict and #conditional-jumps inside the function.
set -uo pipefail
eval "$(opam env)"
cd "$(dirname "$0")"
HARNESS=../calibration/harness.c
mkdir -p bin

CASES="${*:-q_intro1 q_intro2 q_intro3 q_intro4 q_intro5}"
printf "%-10s %-6s %-4s | %-9s | %s\n" cc opt fn verdict "cond-jmps in fn"
printf -- "-----------------------+-----------+----------------\n"
for cc in gcc clang; do
  for opt in O0 O1 O2 O3; do
    for fn in $CASES; do
      b=bin/${fn}_${cc}_${opt}
      $cc -m32 -$opt -no-pie -static -fno-stack-protector "$HARNESS" cases.c \
          -DFUNC=$fn -o "$b" 2>/dev/null || { echo "build fail $b"; continue; }
      v=$(timeout 200 binsec -sse -checkct -sse-script q.cfg -sse-timeout 180 "$b" 2>&1 \
          | grep -oiE "status is : (secure|insecure|unknown)" | grep -oiE "(secure|insecure|unknown)$" | tail -1)
      jmps=$(objdump -d --no-show-raw-insn "$b" | sed -n "/<$fn>:/,/ret/p" \
             | grep -icE "\bj(e|ne|z|nz|g|ge|l|le|a|ae|b|be|s|ns)\b")
      flag=""; [ "$v" = insecure ] && flag=" <== INTRODUCED"
      printf "%-10s %-6s %-4s | %-9s | %s%s\n" "$cc" "$opt" "$fn" "$v" "$jmps" "$flag"
    done
  done
done
