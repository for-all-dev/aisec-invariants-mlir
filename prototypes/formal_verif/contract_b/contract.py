#!/usr/bin/env python3
"""
Layer B — leakage-contract verdict at a chosen observation granularity.

binsec `-checkct` (memory-access) decides the `[ct]` contract: does a load
address depend on the secret at BYTE granularity? That is the input to this
script (`ct_verdict`). Layer B answers the coarser, realistic question:

    program |= [cache-line]  ?

i.e. can an attacker who only sees which 64-byte LINE is touched distinguish two
secrets? A byte-level leak whose reachable addresses all fall in ONE cache line
is SECURE under `[cache-line]`, even though it is insecure under `[ct]`.

The cache-line verdict is COMPUTED from the access layout (element size and
index range, read from layout.tsv — the source ground truth) assuming the table
base is cache-line aligned (the corpus enforces this with __attribute__((aligned(64)))).
For a secret-dependent access base + i*elem, i in [0, index_count):

    distinct_lines = |{ (i * elem) // 64 : i in [0, index_count) }|

    distinct_lines == 1  -> secure   under [cache-line]  (all secrets share a line)
    distinct_lines  > 1  -> insecure under [cache-line]  (secret moves the line)

Usage:  contract.py <kernel> <ct_verdict> [leak_instr]
"""

import os
import sys

LINE = 64  # bytes per cache line (x86)
HERE = os.path.dirname(os.path.abspath(__file__))


def load_layout(path):
    layout = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            kernel, elem, count, aligned, *rest = line.split("\t")
            layout[kernel] = {
                "elem": int(elem),
                "count": int(count),
                "aligned64": bool(int(aligned)),
                "note": rest[0] if rest else "",
            }
    return layout


def cacheline_verdict(spec, ct_verdict):
    """Return (verdict, detail) for the [cache-line] contract."""
    # A coarser observer can never see more than the byte observer: if [ct] is
    # secure the address is secret-independent, so [cache-line] is secure too.
    if ct_verdict != "insecure":
        return ct_verdict, "no secret-dependent address"

    elem, count = spec["elem"], spec["count"]
    if elem == 0 or count <= 1:
        # binsec found a byte leak but the declared layout has no varying index;
        # refuse to soften the verdict rather than guess.
        return "insecure", "byte leak with unknown layout — not softened"

    if not spec["aligned64"]:
        # Without a known-aligned base, a sub-line span can still straddle a
        # boundary; stay conservative.
        return "insecure", "base alignment unknown — conservative"

    lines = {(i * elem) // LINE for i in range(count)}
    span = (count - 1) * elem + elem
    if len(lines) == 1:
        return "secure", f"span {span} B fits 1 cache line"
    return "insecure", f"reaches {len(lines)} cache lines (span {span} B)"


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: contract.py <kernel> <ct_verdict> [leak_instr]")
    kernel, ct_verdict = sys.argv[1], sys.argv[2].lower()
    leak_instr = sys.argv[3] if len(sys.argv) > 3 else "-"

    layout = load_layout(os.path.join(HERE, "layout.tsv"))
    spec = layout.get(kernel)
    if spec is None:
        sys.exit(f"no layout entry for kernel {kernel!r}")

    cl_verdict, detail = cacheline_verdict(spec, ct_verdict)
    print(f"{kernel:<18} | {ct_verdict:<9} | {cl_verdict:<11} | {leak_instr:<11} | {detail}")


if __name__ == "__main__":
    main()
