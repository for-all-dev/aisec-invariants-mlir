# The count channel is confounded by measurement context

Companion to `leak_check.results.siddarth.md` and `leak_check.methodology.siddarth.md`.
Those files are Siddarth's under the repo's `*.<yourname>.md` ownership convention, so
this note records results that bear on their claims rather than editing them. The implied
edits are listed at the end for their author to make or reject.

Code: `leak_check/probe_softmax.py`, `leak_check/probe_softmax_stability.py`,
`leak_check/noninterference.py`, `leak_check/tests/test_count_confound.py`.
Raw evidence: `leak_check/probe_softmax.out`, `leak_check/probe_softmax_stability.out`.

## Config point (PRINCIPLES §2)

**One config point, and not Siddarth's.** His results were taken on torch 2.12.1+cu130,
valgrind 3.22.0, 8 cores (`leak_check.environment.siddarth.md`). These runs: **torch
2.13.0+cpu, valgrind 3.25.1, Python 3.12, 24-core AMD Ryzen AI 9 HX 370, OMP/MKL pinned
to 1 thread, `PYTHONHASHSEED=0`**. Nothing here establishes what his machine did.

## Summary

The softmax lead is retired (§1). Pursuing *why* produced a larger result: at this config
point the instruction-count channel does not measure only the secret. Weights that are
**md5-identical** count `Ir` **99,212** in one measurement condition and **99,707** in
another — a 495 swing carrying no information, larger than any `dIr` this corpus has
called a finding (softmax `-573`, `where_select` `+264`, `branchless` `+11`/`+257`).

The corpus's own negative control fails as a result: `branchless`, a plain
`torch.matmul`, reports DISTINGUISHABLE — verdict AUTHORED against a predicted
`oblivious` (§3). It is not leaking. The classes are loaded from `secrets/zero.npy` and
`secrets/random.npy`, and **the names are different lengths**; measure both at one path
and `dIr` is exactly 0, on both builds, in every context. The corpus was reading its own
filenames.

The criterion now measures each class at a shared, deliberately varied context, which
restores the control (§5). The channel is usable; the single-run inference was not.

`methodology.siddarth.md` licenses a single run per class because `Ir` is "exactly
reproducible". The premise is true and the conclusion still does not follow — §2.

## 1. The softmax lead is retired (measured)

`results.siddarth.md` recorded softmax as an *unverified lead*: oblivious in eager,
`dIr=-573, dBc=-93` compiled — the shape of a compiler-introduced leak. It required three
checks. Two were run; both say no.

**Check A — generated-kernel inspection.**

    cd prototypes/leak_check && uv run python probe_softmax.py      # -> probe_softmax.out

Generated code is identical (normalized) across both classes. The kernel holds no
secret-dependent branch: the only branch-like lines are three copies of
`if(C10_LIKELY(x1 >= 0 && x1 < 512L))`, a bounds guard on a loop index whose trip count is
the compile-time constant `512`. Data operations are branch-free vector code.

Further, the corpus's softmax classes are uniform matrices (`full(0.5)` vs `full(100.0)`),
so `tmp3 = tmp0 - tmp2` is exactly `0.0` for **both**. From the max-subtraction onward the
runs are bit-identical in code *and* data; both outputs are `1/512 = 0.001953125`
elementwise. The secret differs only inside the branchless max-reduction. For these
classes the compiled kernel cannot host a secret-dependent path.

This makes the softmax cell a **degenerate probe**, not merely an unverified one. The bait
targets `exp`'s overflow regime (`|x| > 88`); softmax's max-subtraction cancels it before
the exp. `corpus_activations.secret_classes` gives every non-relu activation the same two
uniform classes. A real softmax probe needs non-uniform rows.

**Check B — within-class repeats** (`probe_softmax_stability.out`) showed the same secret
giving different `Ir`, up to 1,696 — about 3× the `-573`. That retires the lead. What it
means about the instrument is §2, and it is not what the run's own verdict line says.

## 2. Callgrind is exactly reproducible — and that is the problem (measured)

Check B's output concludes "callgrind is not deterministic here". At this config point
that reading is wrong, and the truth is worse.

Repeating a run at a **fixed** path is bit-identical, every time:

    uv run python probe_softmax_stability.py softmax 3     # the original check

- `branchless` eager, same secret, same path, **16/16 runs identical** (`spread=+0`).
- Every kernel-only probe below: `spread=+0` across 3 runs.

So `Ir` *is* exactly reproducible, exactly as the methodology says. But reproducibility
under repetition is not reproducibility under **re-measurement**. Identical data measured
in a different condition gives a different count:

| what changed | content | Ir | Δ |
|---|---|---|---|
| `secrets/random.npy` | random seed 0 | 99,212 | — |
| `scratch/w_rand_seed0.npy` | **md5-identical** | 99,707 | **+495** |
| `secrets/zero.npy` → `scratch/w_zero.npy` | **md5-identical** | 99,485 → 99,466 | −19 |
| `run_all` eager zero, two sessions | **same file** | 138,166 → 138,104 | −62 |

(Byte-identity verified with `cmp` and `md5sum`, not assumed.)

Two *different* draws from the same distribution — carrying the same information, in the
same session, at equal path lengths — also differ:

| weights (kernel only, `branchless`) | Ir | vs zero |
|---|---|---|
| zero | 99,466 | — |
| zero2 (identical content, +1 char in path) | 99,465 | **−1** |
| rand seed 0 | 99,707 | +241 |
| rand seed 1 | 99,564 | +98 |
| ones | 99,288 | −178 |
| half (0.5) | 99,409 | −57 |
| 1e-42 (denormal) | 99,557 | +91 |

Two random draws differ from **each other** by 143. They are the same secret class. Any
`|dIr|` at that scale cannot be attributed to the class distinction.

**Why repetition hides it.** Valgrind disables ASLR, so a run's memory layout is a
deterministic function of its argv/env. Repeat a run unchanged and you re-measure one
layout — bit-identical, spread 0, and every `dIr` looks decisive. But the two secret
classes must differ in *something* (at minimum, the file they load), so the differential
design cannot avoid comparing two conditions. The spread that a repeat reports is
within-condition; the uncertainty that matters is across conditions, and it was never
sampled. "Callgrind is deterministic, so repeat it and see" is therefore
self-confirming.

**Mechanism: unidentified** (hypothesized). Path length shifts everything allocated after
argv, so buffer alignment changing a vectorized kernel's peeling is a candidate; it is
untested, and the ±1-char probe moved `Ir` by only 1. The 495 comparison varied path *and*
session together and does not isolate either. What is established is the operational fact:
identical information, different measurement condition, `Ir` moves by up to ~500.

## 3. The negative control fails (measured)

`branchless` is `torch.matmul(x, self.weight)` — a dense GEMM, which has no
value-dependent path to take. `corpus.EXPECTED` predicts `oblivious`. At this config
point:

    uv run python run_all.py branchless

```
eager    : Ir_zero=138,104  Ir_rand=138,115  dIr=+11   -> DISTINGUISHABLE
compiled : Ir_zero=289,689  Ir_rand=289,946  dIr=+257  -> DISTINGUISHABLE
VERDICT  : AUTHORED   [!! predicted oblivious !!]
```

PRINCIPLES §5 requires a negative control to stay silent. It does not. The single-run
criterion (`ir_diff != 0` ⇒ DISTINGUISHABLE) reports a dense matmul as an authored leak.

The corpus is not wrong about `branchless` — the channel is wrong about `dIr`. Notably an
earlier, colder session of the same command reported `dIr=+282` and verdict
COMPILER-REMOVED: same model, same secrets, a different verdict from a different session.

**The cause is the filename** (measured). Measure both classes at the *same* path and the
difference does not shrink, it vanishes:

```
eager    : Ir_zero=138,062  Ir_rand=138,062  dIr=+0  floor=(Ir 184)    pairs=[0, 0, 0]
compiled : Ir_zero=288,584  Ir_rand=288,584  dIr=+0  floor=(Ir 1,078)  pairs=[0, 0, 0]
VERDICT  : OBLIVIOUS  [MATCHES PREDICTION]
```

Exactly zero, in every context, on both builds. The corpus loads its classes from
`secrets/zero.npy` and `secrets/random.npy` — **names of different lengths**. That
difference, and nothing about the weights, produced the `+11`, the `+257`, and the `+282`.
The nonzero floor (184, 1,078) is the same effect measured deliberately: it is what path
length alone does to a count when the secret is held fixed.

## 4. The measured region contains a value-dependent conversion (measured)

`measured_run.py` counting mode gates the region and then does, inside it:

```python
shim.cg_start()
out = fn(x)
sink = float(out.reshape(-1)[0])   # value-dependent, INSIDE the region
shim.cg_stop()
```

Moving only the sink outside the region (kernel unchanged):

| region | zero | rand | dIr |
|---|---|---|---|
| sink inside (as shipped) | 142,131 | 142,139 | **+8** |
| sink outside (kernel only) | 99,485 | 99,212 | **−273** |

The sink contributes **+281** to `dIr` on its own, and the kernel contributes **−273**;
they nearly cancel to the small positive the harness reports. The region is supposed to
contain the kernel. `float(out[0])` converts a number that differs by class, so a leak in
the *measurement* is being counted as a leak in the *model*. This is separable from §2 and
should be fixed on its own; both effects are present.

## 5. What changed in the criterion

`noninterference._measure_build` no longer takes one run per class. Each repeat presents
the secret at a **deliberately different path length** (`_context`), and both classes are
measured at the **same context per repeat**, so the diff is paired and the layout cancels
inside each pair. Two guards, both required:

- **floor** — how far a count moves when only the context changes and the secret does not.
  A diff under it is manufactured by the harness.
- **stability** — the paired diff must agree across contexts, to within the floor. A
  secret-dependent path gives the same diff in every layout; an artifact does not.

Stability is the guard that generalizes: it catches a *large* artifact, which no magnitude
test can. Agreement is "within the floor" rather than exact, because a real leak that
wobbles by an instruction with layout is still a leak, and only false negatives are
unrecoverable — a rejected artifact still has the taint channel, which needs no magnitude
difference at all.

A count failing either guard is **not interpretable**, which is weaker than *oblivious*
(PRINCIPLES §1).

Pairing turns out to do the heavy lifting: with both classes at one path, `branchless`
counts *identically* (§3), so the floor and stability guards never have to arbitrate. They
matter where a context cannot be shared away — a class whose secret must differ in size,
or a compile cache keyed by content — and as the check that says when a residue is too
small to read.

An earlier version of this change floored on within-class spread at a *fixed* path. It was
useless: that spread is 0 by construction (§2), so the floor read 0 exactly where
protection was needed. It is recorded here because the failure is the point — sampling the
wrong nuisance variable produces a confident zero.

`tests/test_count_confound.py` calibrates the decision logic against these recorded
numbers without valgrind (ms, `uv run pytest`): the artifacts must stay silent,
`cond_skip`/`exp`/taint must still fire.

## 6. What survives

Noise and layout manufacture false positives, never false zeros: no layout makes a
genuinely secret-dependent path count identically in every context. So the corpus's large
positives stand — `cond_skip` (−186,131 / +79,258) and `exp` (+35,061,760) clear anything
here by orders of magnitude, and both are corroborated by taint, which is immune to all of
this. `exp` → COMPILER-REMOVED rests on a 35M difference and a taint report; nothing in
this note touches it.

What does not survive at this config point: any verdict resting on a `|dIr|` of a few
hundred with no taint corroboration. That is softmax's `-573`, `branchless`' `+11`/`+257`,
and `where_select`'s eager `+264` — though `where_select`'s COMPILER-REMOVED verdict rests
on its taint report (`where_select_taint.txt`), not its count, so the verdict stands and
only the `+264` is uninterpretable.

## 7. Claim labels (PRINCIPLES §1)

- **Measured:** codegen identity and absence of a secret-dependent branch in the compiled
  softmax kernel; both softmax classes producing `1/512` exactly; `Ir` bit-identical
  across repeats at a fixed path (16/16); md5-identical weights counting 99,212 vs 99,707;
  two same-distribution draws differing by 143; `branchless` reporting DISTINGUISHABLE;
  the sink's +281 contribution to `dIr`.
- **Measured (added after the re-run):** that the path is the driver for `branchless` —
  holding it fixed makes `dIr` exactly 0 on both builds, and varying it deliberately moves
  a fixed secret's count by 184 (eager) / 1,078 (compiled).
- **Hypothesized:** that path length acts through *buffer alignment* specifically. The
  effect is now pinned to the path; the step from there to alignment is untested, and the
  495 comparison varied path and session together so it isolates neither.
- **Not established:** that Siddarth's `-573` was noise *on his machine* — different config
  point. That softmax is oblivious in any general sense — for these degenerate classes
  there is nothing to leak. That the confound exists on 8-core / torch 2.12 / valgrind
  3.22.

## 8. Open

1. **The mechanism below "the path" is unidentified.** Alignment is the candidate; a
   path-length sweep at constant session, or a fixed-alignment weight buffer, would settle
   it. Pairing already removes the effect for `branchless`, so this is now about
   understanding the instrument rather than rescuing the corpus.
2. **`_context` samples one nuisance variable.** Path length is the knob we can move;
   session-to-session drift (−62 on an unchanged file, §2) is not obviously the same
   effect and is not sampled by it. The floor is a lower bound on the true variability.
3. **The sink belongs outside the region** (§4). Independent of everything else here.
4. **The taint channel remains unrun for softmax** (check 3 of the three). It costs hours
   under `torch.compile`; Checks A and B agree, so this is completeness, not a live
   question.
5. **The softmax probe needs non-uniform rows** before that cell measures anything.
6. **The rest of the corpus has not been re-measured.** `branchless` is re-run and silent
   (§3); `cond_skip`, `where_select`, and the activation sweep are not. Their large
   positives are safe (§6), but every count they report is measured across two filenames
   and so carries the same confound at the ~100s scale.

## 9. Implied edits to Siddarth's files (not made here)

- `results.siddarth.md`: retire the softmax lead (§1) and note the probe is degenerate.
  The `branchless` row's `dIr=+0` does not reproduce at this config point (§3).
- `methodology.siddarth.md` §"Observation channels" 2: "exactly reproducible, so a
  **single** run per class is decisive" — the premise holds under repetition and fails
  under re-measurement (§2). The channel is still the right one; the inference from a small
  nonzero `dIr` is not.

Happy to draft either.
