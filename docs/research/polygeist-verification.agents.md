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

## iter 2026-08-09T17:20Z — target: `scf.while` translation + `--loop-restructure`
Source: `lib/polygeist/Passes/LoopRestructure.cpp` (pass at `tools/cgeist/driver.cc:674`);
transcription from its lit test `test/polygeist-opt/restructure.mlir:4-43` (@kernel_gemm) —
the cf back-edge loop becomes `scf.while` whose before-region recomputes the header,
wraps the body in `scf.if %go`, and forwards exit values through `scf.condition`.
`polygeist.undef` in the carried slot is dead (never read) and transcribed as
`arith.constant false`, said so in the template header. [source]
Expected: the while form CT-PRESERVING and EQUIVALENT (bounded); the do-while twin
CT-BREAKING and NOT-EQUIVALENT.
Measured: `loop_restructure_while.mlir` **VERIFIED** — CT-PRESERVING (obs 8 → 12) +
EQUIVALENT (4 returned values + memory), bounded. [measured]
Control: `loop_restructure_dowhile.mlir` (body hoisted ahead of the first check)
**REJECTED** — CT-BREAKING (obs 8 → 8) as predicted; equivalence measured EQUIVALENT,
*not* the predicted failure, and rightly: the returned flag is `slt(i,0)` over a
non-negative counter, constant false on both sides. The bug is in the trace, not the
value. [measured]
Outcome: translation-written + specified. `scf.while` gained bounded unrolling in
`predication.py` (`run_while`): the before-region runs on every check including the
failing one (that is `scf.condition`'s semantics), so re-running it after exit only
duplicates the exit check — carried values freeze once the condition is false. The old
UNKNOWN coverage control moved from `scf.while` to `cf.switch`
(`templates/switch_unsupported.mlir`), same role, still measured UNKNOWN.
Coverage now: 2/8 steps with a checked template, form 0 = 63.0% of mentions (was
61.9%); `scf.while`/`scf.condition` now translate, 57 unproved ops.
Why: `--loop-restructure`'s entire output shape was behind the missing `scf.while`;
one translation unblocked both the step and 15 corpus mentions.
Next angle: `--polygeist-mem2reg` (`driver.cc:663`) — memref.alloca/load/store to SSA;
the address obligation is the one at stake there.

## iter 2026-08-09T17:55Z — target: `--polygeist-mem2reg` (+ two checker fixes it forced)
Source: `lib/polygeist/Passes/PolygeistMem2Reg.cpp` (`forwardStoreToLoad` at :1075,
pass at `tools/cgeist/driver.cc:663`); transcription from its lit test
`test/polygeist-opt/mem2regIf2.mlir:4-39`, declared deviations in the template header
(f32→i8 — floats untranslatable and upstream's memref model stores bytes;
`llvm.mlir.undef`→named constant, the stronger check; rank-0 memref→memref<1xi8>, which
is what gives the address channel something to observe). `memref.alloca` gained
semantics by aliasing `memref.alloc`'s (the model has no stack/heap distinction);
xdsl has no custom syntax for it, so templates write the generic form. [source]
Expected: mem2reg_if CT-PRESERVING + EQUIVALENT; mem2reg_if_stale CT-PRESERVING +
NOT-EQUIVALENT (a stale forwarding adds no observation; only the equivalence half can
refuse it).
Measured: `mem2reg_if.mlir` **VERIFIED** — CT-PRESERVING (obs 9 → 2; the step removes
the address channel) + EQUIVALENT, values-only (declared, printed). [measured]
Control: `mem2reg_if_stale.mlir` (the second if forwards the pre-if value of m0)
**REJECTED** — CT-PRESERVING as it must be, NOT-EQUIVALENT as it must be. The half
that breaks is exactly the one the 2026-07-29 iteration said was missing. [measured]
Outcome: specified + two checker findings, the second one real:
1. **The strict memory gate cannot pass an allocation-removing rewrite.** Final states
   are compared whole, so a pass whose purpose is deleting allocas always differs.
   Fix: a template may declare `fcvdct.values_only` as a module attribute — the
   equivalence verdict then rests on returned values alone, and both the CLI line and
   the result carry the weakening. (Adding end-of-scope deallocs instead trips an
   upstream verifier error — `ub_effect.ToBoolOp` meets an already-lowered state pair —
   recorded as a dead-end.)
2. **Predicated stores: an encoding fault, found because the CORRECT template failed.**
   The flattener emits both arms of every branch and used guards only on observations,
   so a `memref.store` inside an arm fired on paths that never executed it — corrupting
   the final memory and, through later loads, the values downstream observations see.
   Fixed in `predication.py` (`run_store`): load the old element, store
   `select(guard, new, old)`; the synthetic load is not observed (its address is the
   store's own, which is). The whole corpus keeps its verdicts (79 tests green), so
   this tightened the encoding rather than loosening any prior claim.
Coverage now: 3/8 steps with a checked template, form 0 = 65.8% (memref.alloca's 77
mentions arrived), 56 unproved ops.
Why: mem2reg is the value-shaped pass par excellence; it needed the equivalence gate
(P7) and forced the memory encoding to be honest about guarded stores.
Next angle: `--lower-affine` (`driver.cc:712`) — needs affine.load/store translations,
the 126+95-mention pair, which also unblocks `--affine-cfg`.
