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

## iter 2026-08-09T18:35Z — target: `--lower-affine` (+ the shared-memory fix it forced)
Source: driver.cc:712 invokes mlir's LowerAffine; the llvm-project submodule is NOT
checked out here, so the pass source was fetched from github at the submodule's pinned
SHA 26eb4285 (`git ls-tree HEAD llvm-project`):
mlir/lib/Conversion/AffineToStandard/AffineToStandard.cpp — AffineForLowering
:150-168, AffineLoadLowering :345-361, AffineStoreLowering :388-407. [source]
Translations written: `affine.load`/`affine.store` flatten to `memref.load`/`memref.store`
after map expansion (`expandAffineMap` restricted to dim/const results); xdsl gives both
ops no custom syntax, so templates write the generic form.
Expected: the faithful for+load+store pair CT-PRESERVING + EQUIVALENT; the off-by-one
final index CT-PRESERVING + NOT-EQUIVALENT (a shifted constant address is still
deterministic — the trace cannot tell, the returned element can).
Measured: `lower_affine_for_load_store.mlir` **VERIFIED** — CT-PRESERVING (obs 10 → 18)
+ EQUIVALENT, bounded. Control `lower_affine_wrong_index.mlir` **REJECTED** —
CT-PRESERVING + NOT-EQUIVALENT, exactly the predicted half. [measured]
Outcome: translation-written + specified — after TWO encoding faults surfaced, both
found because the identity template itself failed, and both fixed:
1. **Each of the four CT-query programs got a fresh initial memory** (structural
   `_instantiate`), so source and target of one run read different heaps and a
   memory-reading identity came back ct-breaking. The initial memory is an input:
   source and target of a run now share `memory_in_run{k}`; the two runs stay
   independent. UB isolation survives — only the *initial* state is shared, each
   program threads its own chain.
2. **Unconditionally executed accesses on cut/untaken paths faulted asymmetrically**:
   an exactly-unrolled affine source performs 3 loads where the bounded scf target
   performs 4, and the 4th (guard-false) load could raise UB the source cannot,
   failing equivalence spuriously. Loads and the predicated stores now route their
   indices through `select(guard, index, 0)` — "did not happen" is index 0, in bounds
   for any non-empty memref, and every consumer of the access is guarded anyway.
   Pinned by `test_memory_reading_identity_is_preserving`.
Coverage now: 4/8 steps with a checked template, form 0 = 73.9% of mentions (the
126+95 affine.load/store mentions arrived), 54 unproved ops.
Why: lower-affine is the address-preservation step par excellence — it rewrites every
memory access on the way down, which is why it exercised the memory encoding hard
enough to break it twice.
Next angle: `--affine-cfg` (driver.cc:677, lib/polygeist/Passes/AffineCFG.cpp) — now
that affine.load/store translate, its scf→affine raising can be checked with the same
machinery.

## iter 2026-08-09T18:55Z — target: `--affine-cfg`
Source: `lib/polygeist/Passes/AffineCFG.cpp` (pass at driver.cc:677) —
`MoveStoreToAffine` :1275-1310 raises a memref store whose indices pass `isValidIndex`
into `affine.store`, `fully2ComposeAffineMapAndOperands` folds the feeding arith into
the composed map. Lit test `test/polygeist-opt/affinecfg.mlir:3-28`. [source]
Expected: the composed-map raise CT-PRESERVING + EQUIVALENT; the wrong-stride twin
CT-PRESERVING + NOT-EQUIVALENT (deterministic addresses either way — only the memory
clause can refuse it, and the template returns nothing, so the memory IS the claim).
Measured: `affine_cfg_raise_store.mlir` **VERIFIED** — CT-PRESERVING (obs 4 → 4) +
EQUIVALENT. Control `affine_cfg_wrong_map.mlir` (row stride 2 instead of 3)
**REJECTED** — CT-PRESERVING + NOT-EQUIVALENT, exactly the predicted half; this is the
first template where the whole-memory equivalence clause is the load-bearing one.
[measured]
Outcome: specified, with one declared narrowing and one dead-end worth keeping:
- **Semi-affine products are unrepresentable in xdsl**, full stop: the lit case's
  composed map multiplies by a *symbol* (`%j + %i * (symbol(%arg0) + 1)`) and
  `AffineExpr.__mul__` raises NotImplementedError on any non-constant multiplier — the
  map cannot even be parsed, let alone translated. The template instantiates the
  loop-invariant at the constant 3: same composition code path, symbol half stays
  form 2. `expand_affine_indices` did grow the general affine arithmetic (add/mul over
  dims, symbols, constants; mod/div refused), so constant-coefficient composed maps —
  what `--lower-affine` meets — now translate.
Coverage now: 5/8 steps with a checked template, form 0 = 73.9%, 54 unproved ops.
Why: affine-cfg is the reverse direction of lower-affine (raising, not lowering), and
the address obligation is symmetric — the raised access must touch the same cell on
the same iteration.
Next angle: `--parallel-lower` (driver.cc:744) — but it is polygeist.barrier/parallel
machinery (18 form-2 ops); consider `--convert-scf-to-openmp` (driver.cc:968, 2 form-2
ops) first for the same reason canonicalize-for went first.

## iter 2026-08-09T19:15Z — targets: `--convert-polygeist-to-llvm` (partial), and the two blocked steps
Source: `lib/polygeist/Passes/ConvertPolygeistToLLVM.cpp:2846-2856` — the pass is a
bundle of upstream pattern sets. Its integer-arithmetic slice is llvm-project @
26eb4285 `mlir/lib/Conversion/ArithToLLVM/ArithToLLVM.cpp` (AddIOpLowering :37,
MulIOpLowering :80, SubIOpLowering :104 — 1:1 op mapping); its scf→cf slice enters at
:2848 (`populateSCFToControlFlowConversionPatterns`) and is specified by the general
templates `scf_for_to_cf.mlir` / `scf_if_to_cf.mlir` (both re-verified green today and
now registered for this step). [source, measured]
Expected: the arith slice CT-PRESERVING (vacuously — pure arithmetic emits no
observation, printed as 0) + EQUIVALENT; the swapped-subtraction twin refused by the
equivalence half alone.
Measured: `polygeist_to_llvm_arith.mlir` **VERIFIED** (obs 0 → 0 + EQUIVALENT);
`polygeist_to_llvm_swapped_sub.mlir` **REJECTED** (CT-PRESERVING vacuously +
NOT-EQUIVALENT). [measured]
Outcome for `--convert-polygeist-to-llvm`: specified **partially**, stated plainly:
the memref→llvm slice (getelementptr arithmetic) has NO llvm memory-op semantics
upstream (only integer ops: add/sub/mul/div/shifts/logic) and stays open; `llvm.icmp`
also has no semantics, so the cf→llvm branch slice is not checkable either.
Outcome for `--convert-scf-to-openmp`: **blocked** — the step is
`scf.parallel → omp.parallel/omp.wsloop` (llvm-project @ 26eb4285
SCFToOpenMP.cpp:358-430); the omp dialect is not even loadable in xdsl (measured:
parse error on `"omp.parallel"`), scf.parallel is this corpus's UNKNOWN control, and
the SMT memory model is sequential — concurrency is not a missing translation but a
missing model. Recording UNKNOWN, not a template.
Outcome for `--parallel-lower`: **blocked**, same class — ParallelLower.cpp is
CUDA/GPU machinery (gpu.launch inlining, cudaRT calls, polygeist.barrier), 18 form-2
operations, all parallel-runtime shaped.
Coverage now: **6/8 steps with a checked template**, form 0 = 73.9%, 54 unproved ops.
The remaining two steps need a concurrency model, which no iteration of this loop can
supply honestly; they stay blocked by design, not by neglect.
Next angle: regenerate the artifact (`artifact/collect.py`) so the map reflects
today's five new specifications and the checker fixes; the loop's 8/8 close-out
condition should be re-read as 6/8 + 2 model-blocked, and the closing entry should say
exactly that.
