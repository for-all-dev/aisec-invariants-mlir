---
name: polygeist-verification
description: Cold-restart loop that verifies the Polygeist compiler with prototypes/fcvd_ct. Each invocation reads the durable journal, takes ONE lowering step or ONE missing translation, transcribes it from the pass source with a citation, proves or refutes it with a falsifiable control, records the verdict, and commits. Use to drive Polygeist from zero checked steps to all eight while staying honest.
---

# Polygeist verification — the cold-restart loop

This file is fed to you at the **start of every iteration**. You do **not**
remember previous iterations — your memory between runs is *only the files on
disk*. Read it, do ONE honest step, record it, arm the next wake-up, stop.

The target: **8 of 8 lowering steps of Polygeist carry a checked
specification**, and the operations its pipeline actually uses become
translatable. Baseline at the start: 0 of 8 steps, 59 unproved operations,
61.9 % of operation mentions translatable — the highest of the six compilers
on the map, which is why this one was chosen.

## 1. Orient first (you are cold — do not skip)

1. `docs/research/polygeist-verification.agents.md` — the append-only journal.
   **Read it before choosing a target** so you do not re-walk a dead end. The
   newest entry names the next angle.
2. `prototypes/fcvd_ct/README.md` §`fcvd-ct-lowering` — what a template is and
   what its verdict means.
3. `prototypes/fcvd_ct/compilers/polygeist.json` — the eight steps, each with
   the `file:line` in the Polygeist checkout it was read from.
4. Only the specific pass source you are about to transcribe, in
   `~/third_party/Polygeist` (commit 77c04bb).

Existing work to copy the shape of, not to re-invent:
- `prototypes/fcvd_ct/templates/heir/*.mlir` — a proved pair and its control.
- `prototypes/fcvd_ct/templates/circt/comb_to_arith_div.mlir` — a template
  that is *documented as breaking*; that is a finding, not a failure.
- `prototypes/fcvd_ct/src/fcvdct/tensor_ops.py` — how a missing translation
  gets written (type semantics + operation semantics + a leakage rule).

## 2. Pick exactly ONE target

In leverage order:

1. **A lowering step with no specification.** All eight qualify at the start.
   Prefer the ones whose source is small and declarative; `--canonicalize-for`
   and `--loop-restructure` are loop-shape rewrites and are the natural first
   pair, `--convert-polygeist-to-llvm` is the largest and should come last.
2. **A missing translation that blocks per-program checking.** By use in the
   Polygeist corpus: `affine.load` (126), `affine.store` (95),
   `memref.alloca` (77), `affine.parallel` (63), `polygeist.barrier` (50),
   `affine.if` (32), `polygeist.subindex` (17), `scf.while` (15).
   `affine.load`/`affine.store` with identity maps are the cheapest and unlock
   the most.
3. Whatever the journal flags as the next angle.

If the last two iterations pushed the same target with no movement, switch —
that is what the restart is for.

## 3. Method

1. **Read the pass source** and quote the exact lines the transcription comes
   from. A template header without a `file:line` citation is not admissible.
2. **Cross-check against the pass's own lit test** in `~/third_party/Polygeist/test/`
   where one exists — the CHECK lines say what the pass really emits.
3. **Write the template**: `@source` and `@target` over `fcvd.hole`s for the
   parts the step does not constrain. Say in the header what verdict you
   expect and why, *before* running it.
4. **Write the control.** A "ct-preserving" verdict with no falsifying twin is
   worth little: pair it with a variant that must come back breaking (a branch
   where the real lowering uses a select, an unguarded index, an early exit).
   If the control does not break, your encoding is wrong — fix it, do not
   record the pass.
5. **Run it**: `cd prototypes/fcvd_ct && uv run fcvd-ct-lowering templates/polygeist/<name>.mlir`.
6. **Register it** in `compilers/polygeist.json` with `verifies`, `expect`, and
   `covers` (only for preserving templates), then re-run
   `uv run fcvd-ct-coverage polygeist` — a template counts only while the
   checker still agrees with what the descriptor documents.
7. **Add a test** in `tests/test_polygeist.py` pinning the verdict, and keep
   `uv run pytest`, `ruff check`, `ruff format --check`, `ty check src` green.

## 4. Hard rules — non-negotiable

- **No fabricated verdicts.** Every row in the journal is a verdict the tool
  printed this iteration, with the observation counts it printed.
- **Transcription is the weak link, so cite it.** The proof is about the
  lowering rule as the source states it. If you cannot find the lines, say so
  and pick another target — do not reconstruct a pass from its name.
- **A control that does not break means the encoding is broken.** Never record
  a preserving verdict whose twin also came back preserving.
- **A breaking verdict is a finding, not a failure** — record it with
  `expect: ct-breaking`, and name the operations it accuses in `breaks_ops`
  only when the lowering it describes is one Polygeist actually performs.
- **Unknown is a legitimate outcome.** An operation with no semantics gives
  `unknown`; record it and move to the translation that unblocks it.
- **Commit each finished piece** (the repo's rule), message in the house
  style. **Never push** — this box has no write credentials, and the branch
  has never left it.
- **Do not touch the other five compilers** in this loop.

## 5. Before you exit — record durably

Append one block to `docs/research/polygeist-verification.agents.md`:

```
## iter <UTC> — target: <step or operation>
Source: <file:line in ~/third_party/Polygeist, and the lit test if one exists>
Expected: <the verdict you predicted, written before running>
Measured: <the verdict the tool printed, with observation counts> | blocked: <why>
Control: <the twin and its verdict> | n/a
Outcome: specified | shown-breaking | translation-written | dead-end | blocked
Coverage now: <steps with a specification>/8, <n> unproved ops
Why: <the precise reason, including why measured != expected if so>
Next angle: <a target you did NOT take, for future-you>
```

## 6. Done + arm the next

One target per iteration. You are done for this iteration when the journal
records one of: a step specified, a step shown breaking, a translation written
and its coverage effect measured, or a dead-end with a reason.

Then `ScheduleWakeup` (~600-900 s normally, ~3600 s if near a usage limit),
passing the same loop prompt back. When all eight steps carry a specification,
regenerate the artifact
(`uv run python artifact/collect.py > artifact/translation-map.html` and the
`--standalone` form into `docs/index.html`), write a closing journal entry, and
`ScheduleWakeup stop:true`. If a hard blocker persists across two iterations,
record it and stop rather than spin.
