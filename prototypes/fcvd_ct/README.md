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
- **P5 (done)** — this tool: universal, per-rewrite constant-time preservation.
- P1–P4, P6 — see the plan note. P5 covers rewrites expressible in PDL; C++ conversion patterns
  (which is what `scf`→`cf`→`llvm` lowering is made of) need the per-program checker instead.
