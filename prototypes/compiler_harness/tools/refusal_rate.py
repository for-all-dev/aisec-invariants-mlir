#!/usr/bin/env python3
"""Measure the REFUSAL RATE of the hardened lowering architecture on real code.

Motivation
----------
Every soundness result so far was measured on the harness corpus: 47 fixtures
averaging 7 operations each. The architecture is a refusal architecture -- it
fails closed on absent provenance, unattested provenance, an absent callee
model, or an undischarged observation -- and every one of those fires more often
as code gets larger and messier. A tool that refuses on 40% of real functions is
unusable however sound it is, and nothing in the corpus would reveal that.

The point of this script is that the refusal predicates are STRUCTURAL: they are
properties of the IR and its debug info, not of an information-flow result. So
the refusal rate can be measured before any analysis exists.

What it does NOT measure
------------------------
This is a refusal-rate LOWER BOUND, not a precision figure. A real analysis also
refuses for reasons this script cannot see: an unsupported opcode, a solver
timeout, an unproved alias clause. Those only push the number up. Nothing here
can push it down, so a bad number is decisive while a good number is merely
encouraging.

Usage
-----
    refusal_rate.py <module.ll> [<module.ll> ...]

Reads textual LLVM IR produced with -g. Without debug info every function is
unattested and the rate is trivially 100%, which is itself the correct answer.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

#: Operations whose execution or address is observable to some observer in the
#: model: control flow, memory addresses, calls, allocation sizes. A refusal is
#: only interesting if it lands on one of these.
OBSERVATION = re.compile(
    r"^\s+(?:%\S+\s*=\s*)?(?:(?:musttail|tail|notail)\s+)?"
    r"(br|switch|indirectbr|load|store|atomicrmw|cmpxchg|callbr|call|invoke|alloca|"
    r"getelementptr|udiv|sdiv|urem|srem)\b"
)
#: An observation is attributable only if it carries a source location.
HAS_DBG = re.compile(r"!dbg !\d+")
LLVM_SYMBOL = r'(?:[-A-Za-z$._0-9]+|"(?:[^"\\]|\\.)+")'
DEFINE = re.compile(rf"^define\b.*?@({LLVM_SYMBOL})\s*\(")
#: A function is attested only if it carries a DISubprogram.
DEFINE_DBG = re.compile(r"^define\b.*!dbg !(\d+)")
DECLARE = re.compile(rf"^declare\b.*?@({LLVM_SYMBOL})\s*\(")
CALL_LIKE = re.compile(r"\b(?:callbr|call|invoke)\b")
CALL_TARGET = re.compile(rf"([@%])({LLVM_SYMBOL})\s*\(")
ARTIFICIAL = re.compile(r"DISubprogram\(.*?\bflags:.*?DIFlagArtificial")
SUBPROGRAM = re.compile(r"^!(\d+) = (?:distinct )?!DISubprogram\(")


@dataclass
class FuncStats:
    name: str
    observations: int = 0
    unattributed: int = 0          # observation with no !dbg
    attested: bool = False         # enclosing DISubprogram present
    artificial: bool = False       # compiler-synthesized subprogram
    external_calls: set[str] = field(default_factory=set)

    def refusals(self, modelled: set[str]) -> list[str]:
        """Which refusal predicates fire on this function."""
        out: list[str] = []
        if not self.attested:
            out.append("unattested-provenance")
        if self.artificial:
            out.append("artificial-subprogram")
        if self.unattributed:
            out.append("absent-provenance")
        unmodelled = self.external_calls - modelled
        if unmodelled:
            out.append("absent-callee-model")
        return out


def analyze(path: str) -> tuple[list[FuncStats], set[str], dict[str, int]]:
    text = Path(path).read_text(errors="replace")
    lines = text.splitlines()

    subprograms = {m.group(1) for m in (SUBPROGRAM.match(l) for l in lines) if m}
    artificial_ids = {
        m.group(1)
        for l in lines
        if (m := SUBPROGRAM.match(l)) and ARTIFICIAL.search(l)
    }
    declared = {m.group(1) for l in lines if (m := DECLARE.match(l))}
    defined: set[str] = set()

    funcs: list[FuncStats] = []
    cur: FuncStats | None = None
    for line in lines:
        if (m := DEFINE.match(line)):
            name = m.group(1)
            defined.add(name)
            dbg = DEFINE_DBG.match(line)
            cur = FuncStats(
                name=name,
                attested=bool(dbg) and dbg.group(1) in subprograms,
                artificial=bool(dbg) and dbg.group(1) in artificial_ids,
            )
            funcs.append(cur)
            continue
        if line.startswith("}"):
            cur = None
            continue
        if cur is None or not OBSERVATION.match(line):
            continue
        #: llvm.dbg.* intrinsics are debug bookkeeping, not observations.
        if "@llvm.dbg." in line or "@llvm.lifetime." in line:
            continue
        cur.observations += 1
        if not HAS_DBG.search(line):
            cur.unattributed += 1
        call = CALL_LIKE.search(line)
        if call:
            call_suffix = line[call.end():]
            target = (
                None
                if re.search(r"\basm\b", call_suffix)
                else CALL_TARGET.search(call_suffix)
            )
            if target and target.group(1) == "@":
                cur.external_calls.add(target.group(2))
            else:
                # Indirect calls and inline-asm callbr have no @symbol for the
                # regex above to recover. They still require an explicit model;
                # treating "no name" as "no obligation" is a fail-open parser bug.
                cur.external_calls.add("<indirect-or-inline-asm>")

    # A callee is "modelled" if it is defined in this module. Everything else
    # needs a supplied summary, and absence of one is a refusal.
    for f in funcs:
        f.external_calls = {c for c in f.external_calls if c not in defined
                            and not c.startswith("llvm.")}
    return funcs, defined, {"declared": len(declared)}


def report(path: str) -> None:
    funcs, defined, extra = analyze(path)
    if not funcs:
        print(f"{path}: no defined functions found")
        return

    modelled: set[str] = set()          # nothing supplied: worst case
    fired = Counter()
    refused = 0
    obs_total = obs_unattr = 0
    for f in funcs:
        r = f.refusals(modelled)
        if r:
            refused += 1
            for k in r:
                fired[k] += 1
        obs_total += f.observations
        obs_unattr += f.unattributed

    n = len(funcs)
    print(f"\n=== {path.split('/')[-1]} ===")
    print(f"  functions                      {n}")
    print(f"  policy-relevant observations   {obs_total}  (mean {obs_total // max(n,1)}/fn)")
    print(f"  observations with no !dbg      {obs_unattr}"
          f"  ({100.0*obs_unattr/max(obs_total,1):.2f}%)")
    print(f"  FUNCTIONS REFUSED              {refused} / {n} "
          f"= {100.0*refused/n:.1f}%")
    print("  refusal predicate breakdown (a function may trip several):")
    for k, v in fired.most_common():
        print(f"    {k:26} {v:6}  ({100.0*v/n:5.1f}% of functions)")

    #: The callee-model refusal is the one a summary library could retire, so
    #: report how much of it is concentrated in a few symbols.
    ext = Counter()
    for f in funcs:
        for c in f.external_calls:
            ext[c] += 1
    if ext:
        print(f"  distinct unmodelled callees    {len(ext)}")
        print("  top unmodelled callees (a summary for each retires its refusals):")
        for c, v in ext.most_common(8):
            print(f"    {c:26} called in {v} functions")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        report(p)
