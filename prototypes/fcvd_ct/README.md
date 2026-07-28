# fcvd_ct — constant-time verification inside MLIR, on top of FCVD

Static, SMT-backed counterpart to `mlir_leak` (dynamic) and to `formal_verif`'s binary-level layers
A/B (binsec). Built on **FCVD** = *First-Class Verification Dialects for MLIR* (PLDI'25), whose
implementation is [`opencompl/xdsl-smt`](https://github.com/opencompl/xdsl-smt).

FCVD supplies formal SMT semantics for MLIR operations (values, UB/poison, memory). It has no notion
of *leakage*, so a security property cannot be stated in it as it stands. This package adds the two
missing pieces — an explicit **leakage model** (what an attacker observes) and **self-composition**
(two runs that must stay indistinguishable) — and turns constant-time into one SMT query.

Plan, findings and scope limits: `../../docs/research/fcvd-selfcomposition.agents.md`.

## Setup

```bash
./setup.sh                    # clones xdsl-smt into third_party/ (gitignored), then uv sync
uv run pytest
```

xdsl-smt ships no LICENSE file, so it is deliberately **not** vendored here — it stays an external
checkout, pinned at `dd30235` and installed as an editable path dependency.

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

## `fcvd-ct-lowering` — does a *lowering step* preserve constant-time?

```bash
uv run fcvd-ct-lowering templates/select_to_cf.mlir --counterexample
```

A lowering like `scf.if` → `cf.cond_br` is not a value rewrite on a fixed program: it is a
**structural specification** over arbitrary surrounding code. Written as one — `@source` and
`@target` functions whose unknown parts are `fcvd.hole` operations — it is still a two-program
object, so it takes the same property as above, with stronger quantification: a hole is an
uninterpreted function, so a proof covers *every* program the template can be instantiated with,
not only programs built from operations we gave semantics to.

Two things make the encoding work, and both are checked by mutation tests rather than assumed:

- **Guards.** If-conversion evaluates both arms, so observations carry the path condition they
  happen under and traces are compared as `same guards ∧ (guard → same value)`. Comparing without
  guards makes `if_to_select_leaky` come back *preserving* — a real leak, hidden
  (`test_guards_are_load_bearing`).
- **Hole congruence.** Instances of the same hole are tied by `equal inputs → equal outputs`.
  Removing the axioms does not make the corpus pass, it makes the *correct* lowering fail
  (`test_hole_congruence_is_load_bearing`).

### Measured on the template corpus (2026-07-28)

| template | lowering | verdict |
|---|---|---|
| `scf_if_to_cf` | `scf.if` → `cf.cond_br` + join block | ct-preserving (obs 3 → 3) |
| `if_to_select_pure` | branch over pure code → `arith.select` | ct-preserving (obs 1 → 0) |
| `select_to_cf` | `arith.select` → `cf.cond_br` | **ct-breaking** (obs 0 → 1) |
| `if_to_select_leaky` | branch over *leaking* code → `arith.select` | **ct-breaking** (obs 3 → 2) |
| `swapped_arms` | `scf.if` → `cf.cond_br` with the arms exchanged | **ct-breaking** (obs 3 → 3) |
| `scf_for_to_cf` | `scf.for` → header/body/latch/exit skeleton | ct-preserving, bounded (9 → 8) |
| `scf_for_bounded` | a loop against itself | ct-preserving, bounded (9 → 9) |
| `loop_early_exit` | the loop skeleton plus "leave when the body finds something" | **ct-breaking** (9 → 12) |
| `while_unsupported` | anything with `scf.while` | unknown |

`select_to_cf` is the static counterpart of the `select` kernels `mlir_leak` probes by measurement.
The `if_to_select_pure` / `if_to_select_leaky` pair is the useful one: the two templates differ only
in whether the branch arms leak, and the verdict flips — if-conversion is a hardening for pure code
and a *new* leak for code that touches memory or divides, because the untaken arm now runs too.

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
- P1, P2, P4, P6 — see the plan note. Still open: per-program checking against real `mlir-opt`
  output (which is what closes the gap between the template and the C++ pass), loops, and the
  address rules of the leakage model.
