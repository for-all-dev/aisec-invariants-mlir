# fcvd_ct — constant-time verification inside MLIR, on top of FCVD

Static, SMT-backed counterpart to `mlir_leak` (dynamic) and to `formal_verif`'s binary-level layers
A/B (binsec). Built on **FCVD** = *First-Class Verification Dialects for MLIR* (PLDI'25), whose
implementation is [`opencompl/xdsl-smt`](https://github.com/opencompl/xdsl-smt).

FCVD supplies formal SMT semantics for MLIR operations (values, UB/poison, memory). It has no notion
of *leakage*, so a security property cannot be stated in it as it stands. This package adds the two
missing pieces — an explicit **leakage model** (what an attacker observes) and **self-composition**
(two runs that must stay indistinguishable) — and turns constant-time into one SMT query.

"Safe" here means **functional equivalence together with resistance to timing attacks**, and the two
are independent: a rewrite that returns a stale value adds no observation, and a rewrite that
branches on a secret computes exactly the right answer. `fcvd-ct-lowering` therefore proves both and
reports both. For PDL rewrites the value half is upstream's `verify-pdl`, run beside `fcvd-ct-pdl`
(and, honestly, still run by hand — the table below is transcribed, not re-derived by `pytest`).

Plan, findings and scope limits: `../../docs/research/fcvd-selfcomposition.agents.md`.

## Setup

```bash
./setup.sh                    # clones xdsl-smt into third_party/ (gitignored), then uv sync
uv run pytest                 # asserts every verdict in this file
./run_all.sh                  # prints them all, plus the coverage report
```

The compiler descriptors additionally expect shallow checkouts of circt, heir and onnx-mlir in
`~/third_party` (only for `fcvd-ct-coverage`; the templates and kernels need nothing).

xdsl-smt ships no LICENSE file, so it is deliberately **not** vendored here — it stays an external
checkout, pinned at `dd30235` and installed as an editable path dependency.

## `fcvd-ct` — is *this* labelled kernel constant-time?

```bash
uv run fcvd-ct kernels/secret_index.mlir --counterexample
```

The self-composition driver, i.e. steps 1, 2, 4 and 5 of the plan. An argument marked
`{fcvdct.secret}` (or `{stagingni.protected}`, the marking `prototypes/Staging_NI` already uses) is
free; everything else is *the same SMT constant in both runs*, as is the initial memory. The property
is

    forall public p, secrets s, s'.  L(p, s) = L(p, s')

and it is proved **one obligation at a time**, so a verdict names the channel rather than only
raising an alarm:

| obligation | what it compares | the plan's wording |
|---|---|---|
| `control` | branch conditions, loop trip counts | "conditions and iteration counts are equal in both traces" |
| `address` | `memref.load`/`store` addresses | "computed addresses agree to the bit" |
| `latency` | operands of `div`/`rem` | variable-latency instructions |
| `resource` | allocation sizes, freed pointers | "the sets of allocated and un-freed memory are identical" |

### Measured on the kernel corpus (2026-07-29, z3 4.15.1)

| kernel | verdict | obligation that fails |
|---|---|---|
| `ct_mask` — `(s & 7) + p` | SECURE | — (no observation of any kind) |
| `public_index` — `t[p]` with a secret in the value | SECURE | — (1 address observation, proved equal) |
| `secret_index` — `t[s & 3]` | INSECURE | `address` |
| `secret_branch` — `if s > 0` | INSECURE | `control` |
| `secret_divisor` — `p / s` | INSECURE | `latency` |
| `secret_free` — free one of two buffers by secret | INSECURE | `resource` |
| `unsupported_float` — `f32` | UNKNOWN | — (no float semantics upstream) |

Each violated obligation comes with the two secrets z3 used to separate the traces (`secret1_run0 =
0x3`, `secret1_run1 = 0x0` for the table lookup). A `secure` verdict is always printed with *how
many* observations of that kind existed: zero observations means "nothing of this kind happens here",
which is not the same statement as "checked and proved", and the two must not be read alike.

Scope, stated plainly: secrets are scalar arguments. Secret *memory contents* are not modelled — the
initial memory is shared, so a memref argument is public data — and upstream's `memref` semantics
only handle `i8` elements and static allocation sizes, so a dynamically sized `alloc` is `unknown`
rather than a resource verdict.

## `fcvd-ct-pdl` — does a rewrite preserve constant-time for *every* program it matches?

```bash
uv run fcvd-ct-pdl patterns/shift_to_div.mlir --counterexample
```

For a rewrite from source program S to target program T, with L_X the observations the leakage model
attributes to program X, the tool proves

    forall x, x'.  L_S(x) = L_S(x')  ==>  L_T(x) = L_T(x')

"the rewrite may remove leakage, never add it". No secret/public labelling is needed: the source's
own leakage is the bound, which is what makes the statement hold for every matching program rather
than for one labelled kernel. `unsat` = preserving; `sat` = z3 returns the two inputs that separate
the traces.

### Measured on the corpus (2026-07-28, z3 4.15.1, whole corpus in 5 s)

| pattern | rewrite | `verify-pdl` (values) | `fcvd-ct-pdl` (leakage) |
|---|---|---|---|
| `mul_to_shl` | `x * 8 → x shl 3` | sound | ct-preserving (obs 0 → 0) |
| `div_to_shift` | `x udiv 8 → x lshr 3` | sound | ct-preserving (obs 2 → 0) |
| `rem_idempotent` | `(x urem 8) urem 8 → x urem 8` | sound | ct-preserving (obs 4 → 2) |
| `shift_to_div` | `x lshr 3 → x udiv 8` | sound | **ct-breaking** (obs 0 → 2) |
| `mask_to_rem` | `x and 7 → x urem 8` | sound | **ct-breaking** (obs 0 → 2) |
| `div_swap_operand` | `x udiv 8 → y udiv 8` | unsound | ct-breaking (obs 2 → 2) |
| `unsupported_float` | `x + y → y + x` on f32 | crashes | unknown |

The point of the table is rows 4 and 5: **upstream's verifier proves these rewrites correct, and
they still introduce a timing channel.** Value correctness and constant-time are different
properties, and only one of them was being checked before.

`div_swap_operand` is a control for the checker rather than a plausible rewrite: without a case
where the source already leaks and the target leaks *something else*, a checker that answered
"preserving" whenever the source leaks at all would look just as good on the rest of the corpus.
`unsupported_float` is the coverage control — no float semantics exist upstream, and the answer must
be `unknown`, never a silent `preserving`.

## `fcvd-ct-lowering` — is a *lowering step* safe? (both halves)

```bash
uv run fcvd-ct-lowering templates/select_to_cf.mlir --counterexample
```

A lowering like `scf.if` → `cf.cond_br` is not a value rewrite on a fixed program: it is a
**structural specification** over arbitrary surrounding code. Written as one — `@source` and
`@target` functions whose unknown parts are `fcvd.hole` operations — it is still a two-program
object, so it takes the same property as above, with stronger quantification: a hole is an
uninterpreted function, so a proof covers *every* program the template can be instantiated with,
not only programs built from operations we gave semantics to.

**Safe means two things, and the tool proves them separately.** Constant-time is one half. The
other is that the target still computes what the source computed — and the leakage property cannot
see it: a rewrite that reads a stale value adds no observation, so it passes. So every template gets
two queries, and `VERIFIED` requires both:

| half | question | refuted by |
|---|---|---|
| constant-time | `L_source(x) = L_source(x') ⟹ L_target(x) = L_target(x')` | an observation the target makes and the source did not |
| equivalence | `ub_source ∨ (¬ub_target ∧ returned values agree ∧ memory agrees)` | an input where the two compute different things |

The equivalence half is upstream FCVD's own refinement criterion, UB polarity included, rebuilt over
holes — a source that is already undefined excuses the target, which is what makes it a refinement
and not equality. `--ct-only` asks the leakage half alone and says on stdout that the answer is
partial.

Four things make the encoding work, and all four are checked by mutation tests rather than assumed:

- **Guards.** If-conversion evaluates both arms, so observations carry the path condition they
  happen under and traces are compared as `same guards ∧ (guard → same value)`. Comparing without
  guards makes `if_to_select_leaky` come back *preserving* — a real leak, hidden
  (`test_guards_are_load_bearing`).
- **Hole congruence.** Instances of the same hole are tied by `equal inputs → equal outputs`.
  Removing the axioms does not make the corpus pass, it makes the *correct* lowering fail
  (`test_hole_congruence_is_load_bearing`).
- **Returned values.** Drop them from the equivalence query and the stale-value rewrite comes back
  `equivalent`, which is exactly the blind spot the gate exists to close
  (`test_returned_values_are_load_bearing`).
- **Defined inputs, and exact congruence.** The equivalence query asserts its arguments are not
  poison and relates hole outputs including their definedness. Without the first, CIRCT's guarded
  divisor is refuted; without the second, a *correct* rewrite is refuted, because the accumulated
  result inherits a free poison marker in one program and not the other. Both are false alarms found
  by a control that did not break (`test_defined_inputs_are_load_bearing`,
  `test_exact_hole_congruence_is_load_bearing`). The leakage query keeps the weak axiom and its own
  reason for it.

### Measured on the template corpus (2026-07-29)

| template | lowering | constant-time | equivalence |
|---|---|---|---|
| `scf_if_to_cf` | `scf.if` → `cf.cond_br` + join block | ct-preserving (obs 3 → 3) | equivalent |
| `if_to_select_pure` | branch over pure code → `arith.select` | ct-preserving (obs 1 → 0) | equivalent |
| `select_to_cf` | `arith.select` → `cf.cond_br` | **ct-breaking** (obs 0 → 1) | equivalent |
| `if_to_select_leaky` | branch over *leaking* code → `arith.select` | **ct-breaking** (obs 3 → 2) | equivalent |
| `swapped_arms` | `scf.if` → `cf.cond_br` with the arms exchanged | **ct-breaking** (obs 3 → 3) | equivalent |
| `scf_for_to_cf` | `scf.for` → header/body/latch/exit skeleton | ct-preserving, bounded (9 → 8) | equivalent, bounded |
| `scf_for_bounded` | a loop against itself | ct-preserving, bounded (9 → 9) | equivalent, bounded |
| `loop_early_exit` | the loop skeleton plus "leave when the body finds something" | **ct-breaking** (9 → 12) | equivalent |
| `while_unsupported` | anything with `scf.while` | unknown | unknown |
| `polygeist/canonicalize_for_propagate_value` | `PropagateInLoopBody`, body result returned | ct-preserving (9 → 9) | equivalent, bounded |
| `polygeist/canonicalize_for_propagate_moved_value` | the same rewrite where the pass refuses it | ct-preserving (9 → 9) | **not-equivalent**, bounded |

`select_to_cf` is the static counterpart of the `select` kernels `mlir_leak` probes by measurement.
The `if_to_select_pure` / `if_to_select_leaky` pair is the useful one: the two templates differ only
in whether the branch arms leak, and the verdict flips — if-conversion is a hardening for pure code
and a *new* leak for code that touches memory or divides, because the untaken arm now runs too.

The last two rows are the reason the gate exists, and they are a pair. Polygeist's
`--canonicalize-for` replaces uses of a loop's iteration argument by its init value, and only when
the loop yields that argument back unchanged
(`lib/polygeist/Passes/CanonicalizeFor.cpp:45`). Apply it where that side condition fails and the
body reads a stale value: **the leakage half still says preserving — correctly, since a wrong answer
leaks no more than a right one — and only the equivalence half refutes it.** That blind spot was
recorded in `docs/research/polygeist-verification.agents.md` as a limit of the instrument; it is now
a verdict the tool prints.

### What the equivalence half compares, and what it does not

- **Returned values**, pairwise across return sites: wherever a source path and a target path are
  both taken, their results must agree. Pairing by index would be wrong — after unrolling, the
  target's return sites need not line up with the source's.
- **The memory left behind**, compared whole. This is *stronger* than upstream's block-by-block
  refinement: it also pins the unallocated part and the order blocks were allocated in, so it can
  raise a false alarm on a lowering that reallocates, and cannot pass one that writes different
  bytes. Strict is the safe direction for a gate; the asymmetry is stated rather than assumed away.
- **A template that returns nothing** has only the memory clause behind its `equivalent`, and the
  tool prints which of the two it was. Most of the corpus is in that position — the templates were
  written for the leakage question — so `equivalent` there is a real but thin statement, exactly as
  `secure` with zero observations is. Giving a template results to return is what makes the value
  half bite, and the `canonicalize_for_propagate_value` pair is what that looks like.
- **A hole does not touch memory** (`HoleSemantics` threads the effect state through unchanged), so a
  template whose source models memory-touching code as a hole cannot be checked for equivalence at
  all. `onnx_mlir/gather_to_krnl` is that case: its `@source` is `onnx.Gather` as a pure hole while
  its `@target` stores into `%out`, so the gate reports **not-equivalent**, and the honest reading is
  "this template does not state what is computed", not "onnx-mlir changes the meaning of a gather".
  Checking that one needs real `onnx.Gather` semantics, i.e. a form-2 translation.

### What this does and does not assume

Upstream's `-convert-scf-to-cf` is C++ (`IfLowering`, `ForLowering`, … in
`SCFToControlFlow.cpp`, built on `rewriter.splitBlock`), not generated from a declarative
specification — checked against llvm-project release/18.x. So the proof is about the
**specification** of the lowering, with "the C++ pattern implements this template" as the named
trusted assumption. That assumption is far smaller than trusting the pass outright, and it is
mechanically checkable per-program by translation validation (P1–P4).

Control flow is handled by bounded path walking: every path is followed with its own guard, so
`scf.if` and `cf` graphs flatten into guarded straight-line form (this is also how FCVD's
single-block restriction is worked around) and **loops unroll** — a header is simply re-entered up
to `--unroll` times. A verdict whose paths were cut by that bound is reported as *bounded*, never as
if it held for all iterations. `scf.while` is still refused outright.

`loop_early_exit` is the loop-level counterpart of `select_to_cf`: leaving a scan as soon as the
body finds something is the standard optimisation and the standard way to make the trip count depend
on data. The tool separates it from the honest skeleton, which is the point of having both.

## `fcvd-ct-coverage` — how much of a given compiler can be verified today?

```bash
uv run fcvd-ct-coverage            # all three descriptors in compilers/
uv run fcvd-ct-coverage heir --top 6
```

The plan picks the first compilers to verify by "the fewest translations that are not proved", which
is a question with a number for an answer. The tool counts it: it reads the operations occurring in a
compiler's **own test corpus** and sorts them into the plan's forms — 0 (SMT semantics, read live
from the registry), 1 (covered by a macro-template that still proves — re-run, not trusted), 2
(neither). Descriptors in `compilers/*.json` carry each pipeline as the compiler's own source spells
it, with `file:line` for every step.

Measured 2026-07-29, at circt `2803829`, heir `de797a2`, onnx-mlir `de23de7`:

| compiler | distinct ops | form 0 | form 2 | translatable (by mentions) | steps with a checked specification |
|---|---|---|---|---|---|
| heir | 117 | 34 | **83** | **53.4 %** | 2 / 11 |
| circt | 237 | 49 | 188 | 40.1 % | 2 / 12 |
| onnx-mlir | 302 | 14 | 288 | 33.6 % | 1 / 6 |

## The three compilers

Templates in `templates/<compiler>/` and kernels in `kernels/<compiler>/`, each transcribed from the
pass that implements it, with the file and line in the header comment. Full write-up:
`../../docs/research/compiler-choice-circt-heir-onnx.agents.md`.

| compiler | step | verdict |
|---|---|---|
| CIRCT | `--map-arith-to-comb` (table, div/rem, min/max) | ct-preserving; div/rem 4 → 0, the channel closes |
| CIRCT | `--convert-comb-to-arith` (arcilator's simulation path) | **ct-breaking (0 → 2)** — the simulated divider leaks what the circuit did not |
| HEIR | `--convert-secret-extract-to-static-extract` | closes `address`, **opens `control`** — the emitted `scf.if` branches on `j == secret` |
| HEIR | `--convert-if-to-select` | ct-preserving on a speculatable body, **ct-breaking** on the body HEIR's own pass refuses |
| HEIR | `--mod-arith-to-arith` | **ct-breaking (0 → 2)** — `mod_arith.add` becomes `addi` + `remui` on secret data |
| onnx-mlir | `--convert-onnx-to-krnl` (`onnx.Gather`) | **ct-breaking (0 → 3)** — private indices become addresses, and no hardening pass exists |

Per-program, the same three compilers, `fcvd-ct` on kernels transcribed from each stage:

| kernel | verdict |
|---|---|
| `circt/hw_divide` → `circt/hw_divide_simulated` | SECURE → INSECURE (`latency`) |
| `heir/secret_extract` → `static_extract` → `static_extract_select` | INSECURE (`address`) → INSECURE (`control`) → SECURE |
| `onnx_mlir/gather_secret_index` vs `gather_oblivious` | INSECURE (`address`) → SECURE, 18 observations proved equal |

**The compilers themselves were not run** — none of circt-opt, heir-opt, onnx-mlir is built here, so
every before/after pair is a transcription of the pass source or its lit test, cited line by line.
These are therefore proofs about the *specification* of each step, exactly as for `-convert-scf-to-cf`
above.

## `artifact/` — the translation map

```bash
uv run python artifact/collect.py > artifact/translation-map.html
```

An interactive page over the same data: the dialect graph of all three compilers with the reuse points
marked, every lowering step with the operations that block it, and a cost estimate whose two
assumptions are sliders rather than constants. Everything on it is generated — the graph is the union
of the pipeline steps in `compilers/*.json`, the operation tables are the corpus scan, and each
template is re-run and timed at build time. The only hand-written parts are the prose and the layer
assignment of dialects, which is a judgement about MLIR rather than something the data knows.

## The leakage model

`src/fcvdct/leakage.py`, and every verdict is relative to it:

- integer `div`/`rem` observe **both operands** (variable-latency `idiv` on x86; the same assumption
  layer A's binsec `ct` policy makes on binaries),
- `memref.load`/`store` observe **the address**,
- everything else is assumed constant-latency.

It is a policy object, so a different threat model is a different dict, not a different tool. The
memory rules are implemented but not yet exercised by the corpus: they need function-level
self-composition (P1), since address-shaped rewrites are not what PDL patterns typically express.

## Status

- **P0 (done)** — `poc/run.sh`: the stock refinement predicate cannot double as a CT predicate
  (poison from function arguments makes even a constant-time kernel come back `sat`).
- **P5 (done)** — `fcvd-ct-pdl`: universal, per-rewrite constant-time preservation.
- **P3 (done)** — `fcvd-ct-lowering`: control flow via if-conversion, and lowering steps verified as
  structural specifications over holes.
- **P7 (done)** — the equivalence half of the gate, over the same holes: `check_equivalence` and
  `check_template`, so `VERIFIED` means the step preserves constant-time *and* computes the same
  thing. `fcvd-ct-coverage` will not count a macro-template towards form 1 unless both hold. Still
  open: most templates return nothing, so the value clause is thin for them, and the PDL corpus's
  value column is upstream's `verify-pdl` run by hand rather than from `pytest`.
- **P1/P2 (done)** — `fcvd-ct`: labelled self-composition with the four obligations, and the kernel
  corpus in `kernels/` with both polarities of each.
- **P4 (partly done)** — the differential across a lowering, per compiler: the kernel chains above
  say at which step a channel opens or closes. What is still missing is real compiler output instead
  of transcription.
- **The compiler layer** — `fcvd-ct-coverage`, `compilers/`, and the CIRCT/HEIR/onnx-mlir templates
  and kernels.
- P6, and the honest gaps: `secret.generic` (849 mentions in HEIR's corpus) is not modelled, and no
  compiler was built here, so nothing is checked against real `circt-opt`/`heir-opt`/`onnx-mlir` output.
