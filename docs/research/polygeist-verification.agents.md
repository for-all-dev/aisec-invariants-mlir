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

## iter 2026-07-29T12:40Z — target: `--canonicalize-for`, pattern `PropagateInLoopBody`
Source: `lib/polygeist/Passes/CanonicalizeFor.cpp:26-51` (pass at `tools/cgeist/driver.cc:685`).
The rule fires only when an iteration argument is yielded back unchanged
(`iterOperand == yieldOperand`), and then replaces uses of the region argument by the
init value. No lit test for this pattern alone. [source]
Expected: CT-PRESERVING for the pattern, CT-BREAKING for the twin that applies the same
replacement where the body *does* modify the argument.
Measured: both CT-PRESERVING, 17 → 17 observations, bounded. [measured]
Control: `canonicalize_for_propagate_moved.mlir` — **did not falsify**, and after
analysis that is the right answer, not a blind spot. Reading a stale value is a value
bug; the property proved here is that a rewrite may remove leakage and never add it. The
target calls the body only with `%init`, which is what the source passes on its first
iteration, so congruence ties the target's observations to ones the source already makes
— the target leaks a strict subset. Nothing added, nothing reported.
Outcome: specified (weakly) + a fix to the checker, described below.
Coverage now: 1/8 steps with a checked template, 59 unproved ops (unchanged — this
template covers no new operation).
Why: two things came out of this iteration, and the second matters more.

1. **An encoding fault, found by the control and fixed.** The first run reported *both*
   templates CT-BREAKING, including the one that must preserve. Cause: hole congruence
   compared raw (value, poison) pairs, while `traces_agree` had always compared values
   only. Unrolling a loop whose bound is a function argument builds
   `select(keep_going, new, old)`, and `keep_going` inherits that argument's poison — so
   the hole's inputs differed in the poison bit alone, congruence never fired, its
   outputs were unconstrained, and a correct rewrite came back as a leak. Confirmed by
   re-running the same template with constant bounds, which passed. `structural.py` now
   compares values in congruence too. Every other template in the corpus keeps its
   verdict, and the 61 tests stay green, so this unblocked loops rather than loosening
   anything. This is the same poison-from-arguments family as the P0 finding in
   `fcvd-selfcomposition.agents.md`.
2. **This pass is the wrong shape for this instrument.** Its side condition is about
   functional equivalence, and the leakage property cannot falsify a value bug by
   construction. Checking it needs the value-refinement criterion — upstream FCVD's,
   which our checkers deliberately switch off — not this one. A "specified" verdict here
   is therefore real but thin: it says the rewrite adds no observation, which was never
   in doubt.
Next angle: `--loop-restructure` (`driver.cc:674`,
`lib/polygeist/Passes/LoopRestructure.cpp`) — it rebuilds `cf` back-edges into `scf`
loops, so its side condition *is* about control flow, and a wrong trip count would show
up in the trace. That is a pass where a control can actually break, unlike this one.
