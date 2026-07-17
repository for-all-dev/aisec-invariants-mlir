#!/usr/bin/env bash
# A COMPILER-INTRODUCED weight-confidentiality leak.
#
# `mm_codebook_ct` (cases.c) is a constant-time codebook dequant: it reads ALL
# codebook entries at PUBLIC addresses and mask-selects the one at the secret
# index — branchless by construction, oblivious at -O0. This sweep shows that
# **clang -O1 lowers the mask-select back into a secret-dependent branch**,
# re-introducing exactly the leak the source was written to avoid. The leak is
# added by the *compiler*, not by the source — gcc and clang -O2/-O3 keep it
# oblivious.
#
# Drives the reusable ctverify package (binsec -checkct) across gcc/clang × -O0..-O3.
set -uo pipefail
eval "$(opam env)"
cd "$(dirname "$0")"
CTV=(uv run --project ../ctverify --quiet ctverify)
mkdir -p bin

echo "kernel: mm_codebook_ct  (constant-time weight dequant; secret = W[])"
printf "%-8s | %-5s | %-9s | %s\n" "cc" "opt" "verdict" "leak channel"
printf -- "---------+-------+-----------+---------------------------\n"
for cc in gcc clang; do
  for opt in O0 O1 O2 O3; do
    b="bin/ctct_${cc}_${opt}"
    if ! $cc -m32 -"$opt" -no-pie -static -fno-stack-protector \
         harness.c cases.c -DFUNC=mm_codebook_ct -o "$b" 2>/dev/null; then
      printf "%-8s | %-5s | %-9s |\n" "$cc" "$opt" "build-fail"; continue
    fi
    line=$("${CTV[@]}" checkct "$b" --cfg w.cfg --features ct)
    verdict=$(awk '{print $1}' <<<"$line")
    leak=$(sed 's/.*leaks=//' <<<"$line")
    printf "%-8s | %-5s | %-9s | %s\n" "$cc" "$opt" "$verdict" "$leak"
  done
done

cat <<'NOTE'

=> clang -O1 is INSECURE (control-flow): the compiler introduced a
   secret-dependent branch into constant-time source. gcc (all -O) and
   clang -O2/-O3 keep it oblivious. Confirm the branch with:
     objdump -d -M intel bin/ctct_clang_O1 | sed -n '/<mm_codebook_ct>:/,/ret/p'
   (cmp <secret idx>, j ; jne  — the load is now behind a secret-dependent jump)
NOTE
