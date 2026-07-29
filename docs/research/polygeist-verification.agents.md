# Verifying Polygeist — the autonomous loop's journal

Append-only. Newest entry last; its **Next angle** is the plan. Written by the
cold-restart loop in `.claude/skills/polygeist-verification/SKILL.md`, which is
the authority on method and on the rules that keep it honest.

Claim discipline as elsewhere in `docs/research/`: **[source]** = read from
Polygeist's own code at commit `77c04bb`, **[measured]** = printed by the tool on
this box, **[inference]** = reasoning not yet checked.

## Why Polygeist

Of the six compilers on the map it has the most translatable corpus — 61.9 % of
operation mentions, against 53.4 % for HEIR and 17.3 % for torch-mlir — and only
59 unproved operations, because it speaks the shared caskets (`affine`, `scf`,
`memref`, `arith`) rather than a dialect of its own invention. It is therefore
the compiler most likely to be verified end to end rather than in patches.
[measured, 2026-07-29]

## Baseline before the loop starts [measured, 2026-07-29]

Eight steps, read from `tools/cgeist/driver.cc`, **none** with a checked
specification:

| step | source | form 0 | form 2 |
|---|---|---|---|
| `--polygeist-mem2reg` | driver.cc:663 | 4 | 5 |
| `--loop-restructure` | driver.cc:674 | 5 | 5 |
| `--affine-cfg` | driver.cc:677 | 5 | 8 |
| `--canonicalize-for` | driver.cc:685 | 3 | 4 |
| `--lower-affine` | driver.cc:712 | 2 | 4 |
| `--parallel-lower` | driver.cc:744 | 3 | 20 |
| `--convert-scf-to-openmp` | driver.cc:968 | 3 | 4 |
| `--convert-polygeist-to-llvm` | driver.cc:1009 | 24 | 32 |

The operations that block per-program checking, by use in Polygeist's own test
corpus: `affine.load` 126, `affine.store` 95, `memref.alloca` 77,
`affine.parallel` 63, `polygeist.barrier` 50, `affine.if` 32,
`polygeist.subindex` 17, `scf.while` 15.

## Plan

Steps first — they are the deliverable and each is one template plus its
control. Translations second, cheapest-and-most-used first
(`affine.load`/`affine.store` with identity maps), since they are what turns a
specification proof into a per-program one.

Definition of done: eight of eight steps carry a verdict the coverage counter
re-checks, every preserving verdict has a falsifying twin, and the artifact is
regenerated from live data.

## iter 2026-07-29T12:00Z — target: none yet, loop armed
Source: n/a
Expected: n/a
Measured: baseline above [measured]
Control: n/a
Outcome: blocked — nothing attempted yet, this entry exists so the first cold
restart has something to orient on
Coverage now: 0/8, 59 unproved ops
Why: the loop is being set up, not run
Next angle: `--canonicalize-for` (driver.cc:685, pass in
`lib/polygeist/Passes/CanonicalizeFor.cpp`) — a loop-shape rewrite, the smallest
declarative surface of the eight, and the natural first pair with its control.
