"""
Check A of the softmax lead (see results.siddarth.md, "softmax: an UNVERIFIED lead").

softmax measured oblivious in eager but dIr=-573, dBc=-93 in compiled — the shape
of a compiler-introduced leak (the empty quadrant). The taint channel was never run
for it because torch.compile under memcheck costs hours. This probe is the cheap
check to run FIRST: read the generated kernel.

Two questions, in order of what they can settle:

  A1. Is the generated code identical across the two secret classes?
      Inductor keys codegen on shape/dtype, not values, so "identical" is expected.
      A difference would mean the secret steered codegen at compile time.

  A2. Does the generated softmax kernel contain a value-dependent branch at all?
      If A1 says the machine code is identical for both classes, then a nonzero dIr
      must come from either (a) a data-dependent branch INSIDE that fixed code
      taking a different path per class, or (b) something outside the kernel
      (allocator, dispatch, guards). A2 discriminates: no branch in the kernel
      means the dIr cannot be a kernel-level secret-dependent path.

Reuses probe_autotune.normalize — the POST-BUGFIX normalizer. The original bug (an
unstripped "V0703 HH:MM:SS.mmm PID ...]" TORCH_LOGS prefix making every line differ
by timestamp) is what manufactured the max-autotune false positive; do not
reimplement it here.

    python probe_softmax.py             # softmax (default)
    python probe_softmax.py exp         # any activation in corpus_activations
"""

import difflib
import os
import re
import subprocess
import sys

import run_activations as RA
from probe_autotune import normalize

HERE = os.path.dirname(os.path.abspath(__file__))

# Control-flow constructs that would make the kernel's execution value-dependent.
# A vectorized blend (blendv / vec::minimum / where) is branch-free and does NOT
# count -- that is the where_select lesson: data-dependent VALUE, oblivious
# EXECUTION.
BRANCH_PAT = re.compile(r"\bif\s*\(|\bfor\s*\(.*\bif\b|\?\s*[^:]+\s*:|\bgoto\b|\bwhile\s*\(")
BRANCHFREE_PAT = re.compile(r"blendv|vec::maximum|vec::minimum|where|clamp|masked", re.I)


def run(act, secret_path):
    env = dict(
        os.environ,
        TORCH_LOGS="output_code",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        PYTHONHASHSEED="0",
    )
    p = subprocess.run(
        [sys.executable, "_softmax_worker.py", act, secret_path],
        cwd=HERE,
        capture_output=True,
        text=True,
        env=env,
        timeout=1800,
    )
    result = None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT"):
            result = line
    if result is None:
        raise RuntimeError(f"{secret_path}: no RESULT\nSTDERR tail:\n{p.stderr[-2000:]}")
    return result, normalize(p.stderr), p.stderr


def kernel_body(raw):
    """Pull the generated C++ kernel out of the raw output_code dump, prefix-stripped."""
    prefix = re.compile(r"^V\d+ [\d:.]+ \d+ [^\]]*\] \[[^\]]*\] \[__output_code\] ?")
    lines = [prefix.sub("", ln) for ln in raw.splitlines()]
    body, on = [], False
    for ln in lines:
        if 'extern "C"' in ln or "cpp_fused" in ln or "#pragma" in ln:
            on = True
        if on:
            body.append(ln.rstrip())
    return "\n".join(body)


def main():
    act = sys.argv[1] if len(sys.argv) > 1 else "softmax"
    la, pa, lb, pb = RA.gen(act)

    print(f"Check A — generated-kernel inspection for `{act}`")
    print(f"classes: {la} vs {lb}  (from corpus_activations.secret_classes)\n")

    res_a, code_a, raw_a = run(act, pa)
    res_b, code_b, raw_b = run(act, pb)
    print(f"  {res_a}")
    print(f"  {res_b}\n")

    same = code_a == code_b
    print(f"A1. generated code identical (normalized): {same}")
    if not same:
        d = list(
            difflib.unified_diff(
                code_a.splitlines(), code_b.splitlines(), fromfile=la, tofile=lb, lineterm="", n=2
            )
        )
        print(f"    codegen DIFFERS — {len(d)} diff lines; first 40:")
        for ln in d[:40]:
            print("      " + ln)
        outp = os.path.join(HERE, "secrets", "act")
        os.makedirs(outp, exist_ok=True)
        for lab, code in ((la, code_a), (lb, code_b)):
            with open(os.path.join(outp, f"{act}_code_{lab}.txt"), "w") as f:
                f.write(code)
        print(f"    full normalized dumps written to secrets/act/{act}_code_*.txt")

    body = kernel_body(raw_a)
    branches = [ln.strip() for ln in body.splitlines() if BRANCH_PAT.search(ln)]
    blends = [ln.strip() for ln in body.splitlines() if BRANCHFREE_PAT.search(ln)]
    print(f"\nA2. branch-like lines in generated kernel: {len(branches)}")
    for ln in branches[:15]:
        print("      " + ln)
    print(f"    branch-free select/blend lines: {len(blends)}")
    for ln in blends[:10]:
        print("      " + ln)

    print(f"\n--- generated kernel (class {la}) ---")
    print(body if body.strip() else "(no kernel body captured)")


if __name__ == "__main__":
    main()
