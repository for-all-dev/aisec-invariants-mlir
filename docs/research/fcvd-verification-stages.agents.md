# How the MLIR verifier works: semantic, timing, and cache leaks, stage by stage

Audience: an agent (or a person) who has never seen this repository and is about to
verify an MLIR compiler with it. This file explains the method; it contains no results.
Everything described here is implemented in [`prototypes/fcvd_ct/`](../../prototypes/fcvd_ct/)
on top of FCVD (*First-Class Verification Dialects for MLIR*, PLDI'25 — the
`opencompl/xdsl-smt` project). The full engineering history is in
[`fcvd-selfcomposition.agents.md`](fcvd-selfcomposition.agents.md); this file is the
distilled "how it works".

## What is being proved

A compiler is a chain of lowering steps (`scf → memref → llvm`, rewrites,
canonicalizations). The claim we care about: **no step turns safe code into unsafe
code.** "Safe" is two properties, and both must be proved — each one alone is not the
claim:

1. **Functional equivalence** (the *semantic* half): after the step, the program still
   computes the same values and leaves memory in the same state. A step that changes
   results is a miscompilation, and no security statement survives it.
2. **Leakage resistance** (the *side-channel* half): an observer who cannot read the
   program's values but can watch *how it executes* — which branches it takes, which
   memory addresses it touches, which variable-latency instructions it runs — learns
   nothing about the secrets.

Both halves are decided by the same machine: translate the program(s) into SMT formulas,
assert the negation of the property, and ask z3. `unsat` means the property is proved
for **all** inputs; `sat` means the solver found a concrete counterexample and prints it.

## The three leak classes, and which check catches which

| leak class | what actually leaks | caught by |
|---|---|---|
| **semantic** | the values themselves: a step changes what the program computes or returns | the equivalence query (`check_equivalence` / upstream `verify-pdl`) |
| **timing** | which path executed and how long ops took: secret-dependent branches, trip counts, `div`/`rem` operands | the `control` and `latency` obligations |
| **cache** | which memory addresses were touched — the thing a cache attacker reconstructs from cache lines | the `address` obligation (plus `resource` for alloc/free patterns) |

The cache check works at **bit granularity of the address**: if a secret can move a
load/store address by even one bit, the verdict is INSECURE. This is deliberately
stricter than a real cache attacker (who only resolves 64-byte lines), so a SECURE
verdict here is stronger than "safe against Flush+Reload". The coarser cache-line
contract exists at the *binary* level (`prototypes/formal_verif/contract_b/`) and is a
separate layer, not part of this pipeline.

## The five stages of a leakage proof (`fcvd-ct`, one kernel)

### Stage 1 — mark the secrets

The input is ordinary MLIR. One or more function arguments carry an attribute that
declares them secret:

```mlir
func.func @lookup(%table: memref<8xi8>, %s: index {fcvdct.secret}) -> i8
```

Three spellings are accepted — `fcvdct.secret`, `stagingni.protected` (what
`prototypes/Staging_NI` writes), and `secret.secret` (what HEIR's own `--secretize`
emits) — so kernels from those tools need no re-annotation. Everything not marked is
public. **An unlabelled kernel has no property to prove and the tool answers `unknown`,
never `secure`.**

### Stage 2 — run the program twice, virtually (self-composition)

Leakage freedom is a statement about *two* executions:

```
forall public p, secrets s, s'.   L(p, s) = L(p, s')
```

— whatever the observer sees (`L`) must be identical for any two secrets, given the same
public inputs. So the kernel is lowered into the SMT module **twice**:

- every **public** argument is *the same SMT constant* in both runs (`public0`, …);
- the **initial memory** is one shared state (`memory_in`);
- every **secret** argument becomes two independent constants
  (`secret1_run0`, `secret1_run1`).

Sharing the public constants (instead of declaring two and asserting them equal) keeps
the formula smaller and makes counterexamples readable: the only free variables are the
things allowed to differ, i.e. the secrets.

### Stage 3 — translate every operation into formulas, and record what it leaks

FCVD gives each MLIR operation an SMT semantics: values are (bitvector, poison) pairs,
memory is an effect threaded through the program and lowered to SMT arrays, UB is a
flag. Lowering a function replaces each op with its formula.

FCVD by itself only models *values*. The side-channel half needs one more ingredient —
a **leakage model**: a table saying which operations an attacker observes and which
operands the observation consists of ([`src/fcvdct/leakage.py`](../../prototypes/fcvd_ct/src/fcvdct/leakage.py)):

| observed operation | what is recorded | obligation |
|---|---|---|
| a branch / loop bound | the condition, the trip count | `control` |
| `memref.load` / `memref.store`, `tensor.extract` / `tensor.insert` | the index operands (the address) | `address` |
| `arith.divsi/divui/remsi/remui/...` | both operands (x86 `div` latency depends on them) | `latency` |
| `memref.alloc` / `alloca` / `dealloc` | the size / the freed block | `resource` |

Observations are captured *while* the program is lowered to SMT, not by instrumenting
the IR beforehand — that is what lets the same recorder work on symbolic PDL patterns
that never exist as concrete IR. Everything absent from the table (shifts, multiplies,
boolean ops) is assumed constant-time; every verdict is relative to this model.

Control flow (`scf.if`, bounded `scf.for`/`affine.for`) is handled by if-conversion:
branches become guards, loops with constant bounds are unrolled. An observation is
recorded *together with the guard under which it happens*.

### Stage 4 — one obligation at a time

For each obligation kind (`control`, `address`, `latency`, `resource`), build one query:

1. take only the observations of that kind from both traces;
2. build `traces_agree` = for every pair of corresponding observations:
   `guard_A = guard_B` **and** `guard_A ⇒ (value_A = value_B)` — the guard is compared
   as well as the value, so "the two runs took different paths" surfaces as a `control`
   violation instead of a spurious value mismatch elsewhere;
3. assert `not(traces_agree)` and `check-sat`.

Checking obligations separately is what makes a verdict *name the channel*: "INSECURE
because `address`" is the cache leak; "INSECURE because `control`" is the branch leak.
One combined query would only say "leaks somewhere".

### Stage 5 — the verdict

| solver answer | verdict | meaning |
|---|---|---|
| `unsat` | SECURE | proved for **all** inputs, under this leakage model |
| `sat` | INSECURE | z3 prints the two secret values that separate the traces (e.g. `secret1_run0 = 0x3`, `secret1_run1 = 0x0` for a table lookup) |
| timeout / error / unsupported op | UNKNOWN | **never folded into secure** |

Two honesty rules are built into the output and must be preserved by anyone reporting
these results:

- Every SECURE line prints *how many observations of that kind existed*. "SECURE
  (0 observations)" means "nothing of this kind happens in this kernel" — vacuous —
  and must never be read as "checked and proved equal".
- If a loop was cut by the unrolling bound, the result is flagged `bounded`: the
  verdict covers those iterations only.

## The equivalence half (the semantic leak)

The leakage query compares *observations* and by construction cannot notice that a step
changed the *result*. So VERIFIED always requires a second, independent query:

- for **PDL rewrites**, upstream's `verify-pdl` proves value refinement for all programs
  the pattern matches;
- for **structural macro-templates** (see below), `structural.check_equivalence` relates
  what the two programs return and the memory they leave behind, under upstream's own
  refinement criterion including UB polarity (`ub_source ∨ (¬ub_target ∧ agree)`).

Two encoding traps live here, both already burned into the code — do not "simplify" them
away: the equivalence query must assert its arguments are **non-poison** (otherwise a
free poison bit makes even the identity rewrite fail), and it must relate hole outputs
*including* their poison bit — unlike the leakage query, which deliberately compares
values only.

## Four tools, four scopes

| tool | question it answers | quantifies over |
|---|---|---|
| `fcvd-ct` | is *this* labelled kernel leak-free? | one program, all inputs |
| `fcvd-ct-pdl` | does *this rewrite rule* preserve leak-freedom? | **all programs** the pattern matches |
| `fcvd-ct-lowering` | does *this lowering step* (given as a before/after template with `fcvd.hole` placeholders) preserve both halves of safe? | all instantiations of the holes |
| `fcvd-ct-coverage` | how much of a *compiler* can be checked today? | the compiler's own test corpus |

`fcvd-ct-coverage` sorts every operation the compiler's corpus mentions into three
forms: **form 0** — has SMT semantics (directly translatable), **form 1** — covered by a
macro-template proved once (both halves) and applied thereafter without re-proof,
**form 2** — untranslatable today, i.e. the frontier where new work goes. Macro-templates
are the economics of the whole method: a translation is written once and every later
proof reuses it.

## Verifying a compiler step: the workflow

1. **Pick the step** (a pass, a rewrite, one lowering) and obtain its before/after IR.
   Best: run the compiler itself. If the compiler is not built on the box, transcribe
   the pair from the pass source or its lit test, **citing file:line** — and say
   explicitly that the proof is about the step's specification, not the binary's output.
2. **Label the secrets** in the *before* kernel (stage 1 above).
3. **Run `fcvd-ct` on both** the before and the after kernel. The interesting signal is
   the *delta*: a step is ct-breaking when the before-verdict is SECURE and the
   after-verdict is INSECURE (or when an obligation's observation count goes 0 → n).
   A step can also *shift* a leak between channels — HEIR's
   `--convert-secret-extract-to-static-extract` closes `address` but opens `control` —
   so compare per obligation, not just the headline verdict.
4. **If the step is a PDL pattern**, run `fcvd-ct-pdl` + `verify-pdl` instead: one proof
   for all matching programs. **If it is a C++ conversion pattern**, express it as a
   before/after macro-template with holes and run `fcvd-ct-lowering`.
5. **Report** the verdict with: the leakage-model version, the obligation counts, any
   `bounded` flag, and the counterexample secrets for INSECURE. Never report a verdict
   the tool did not print in this run.

## Known limits (state them with every result)

- Secrets are **scalar arguments**; secret *memory contents* are not modelled (the
  initial memory is shared, so a memref argument's data is public).
- **Floats are untranslatable** upstream → `unknown`. Denormal-latency leaks are caught
  by the binary-level layers (`prototypes/formal_verif/`), not here.
- Loops are proved by **exact unrolling of constant bounds**; secret-dependent trip
  counts show up as `control` leaks, but unbounded loops make the result `bounded`.
- The verdict is relative to the **leakage model**: channels absent from the table
  (speculation, prefetchers, port contention, power) are out of scope at this level.
- Address granularity is the **bit**, not the cache line — conservative in the safe
  direction (see the leak-class table above).

## Commands

```sh
cd prototypes/fcvd_ct
uv run fcvd-ct kernels/secret_index.mlir --counterexample   # one kernel, name the channel
uv run fcvd-ct-pdl patterns/<rewrite>.mlir                  # one rewrite, all programs
uv run fcvd-ct-lowering templates/<step>.mlir --unroll 8    # one lowering step, both halves
uv run fcvd-ct-coverage heir                                # forms 0/1/2 (descriptors in compilers/*.json)
./run_all.sh                                                # everything, verdicts pinned by pytest
uv run pytest                                               # the verdicts as tests
```
