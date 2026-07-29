# FCVD + self-composition: proving constant-time preservation inside MLIR

Plan note for branch `fcvd-mlir-noninterference`. Follows the claim discipline of
`../../prototypes/leak_check/PRINCIPLES.md`: **[source]** = read from the tool's live source or a
paper, **[measured]** = our own run on this box (2026-07-28, Xeon 8168), **[inference]** = our
reasoning, not yet checked.

Companion to `mlir-tv-custom-dialect.agents.md`, which surveyed the same problem for *mlir-tv* and
concluded that the non-interference route (Route A) required forking a C++ encoder. **This note
revises that conclusion for FCVD**: FCVD's implementation is extensible from the outside, so Route A
no longer needs a fork.

## 0. What FCVD actually is, and what we cloned

"FCVD" = **First-Class Verification Dialects for MLIR**, Fehr/Grosser/Regehr et al., PLDI 2025
(doi 10.1145/3729309). The implementation is **`opencompl/xdsl-smt`** — Python, on top of xDSL, not
a C++ MLIR fork. [source] Cloned to `~/third_party/xdsl-smt` @ `dd30235`, venv in its `.venv`
(`uv venv` + `uv pip install -e '.[dev]'`, xdsl 0.48.3 + z3-solver 4.15.1). [measured]

Its own test suite here: **171 passed / 6 failed / 5 xfail** (52 s). The 6 failures are in
`tensor-theory`, `superoptimize` and `xdsl-smt-run` — none on the `lower-to-smt`, `xdsl-tv`,
`verify-pdl` or `memref` paths we need. [measured]

What we get for free:

- **SMT semantics with UB and poison** for `builtin`, `func`, `arith`, `comb`, `llvm` (integer ops),
  `memref` (alloc/dealloc/load/store), plus `pdl` and the `transfer` dialect. [source:
  `xdsl_smt/semantics/`] The paper's headline five are `arith`, `func`, `builtin`, `memref`, `comb`;
  `llvm` arrived after the paper.
- **A real memory model**: memory is an effect threaded through the program (`effects/memory_effect`,
  `effects/ub_effect`), lowered to SMT arrays by `LowerMemoryToArrayPass`. Alloc/dealloc are part of
  the state, so "no memory left allocated that shouldn't be" is expressible. [source]
- **A working relational harness**: `xdsl-tv before.mlir after.mlir | z3` builds one SMT module
  containing both programs, asserts `not(refinement)` and `check-sat`. SAT = counterexample. That is
  exactly the shape a 2-safety check needs. [source: `xdsl_smt/cli/xdsl_tv.py`]
- **`verify-pdl`**: proves a *rewrite rule* correct for **all** input programs it matches — the only
  component in the ecosystem that verifies a transformation universally rather than per-program.
  [source]
- **Extension points, no fork needed**: op semantics are entries in Python dicts
  (`SMTLowerer.op_semantics`, `type_lowerers`, `attribute_semantics`), registered at load time by
  `load_vanilla_semantics()`. New dialects and new lowering steps are added from an external package.
  [source: `xdsl_smt/passes/lower_to_smt/smt_lowerer_loaders.py`] **This is the difference from
  mlir-tv** (hardcoded C++ `encodeOp` overload table, no plugin API) and it is why the earlier note's
  "Route A = C++ fork + pinned LLVM" cost estimate does not apply here.

## 1. The gap between the marketing story and the code

The 5-step story ("mark secrets → duplicate the trace → translate every op to predicates → three
security obligations → SAT/UNSAT verdict") is the right architecture, but only step 3's *arithmetic
and memory* part exists today. Four things are missing, and they are the actual work:

1. **There is no leakage model.** FCVD's semantics model *values and memory state*, never an
   *observation trace*. Constant-time is a property of the trace (which branches were taken, which
   addresses were touched, which variable-latency instructions ran), and none of that is emitted by
   the SMT lowering. [source] We have to define what an attacker observes and make it a first-class
   output. Without this step, self-composition proves nothing about timing.
2. **There is no self-composition driver.** `xdsl-tv` relates *two different programs on the same
   inputs*. We need *one program on two input vectors that agree on the public part*. Same plumbing,
   different quantifier structure — a new driver, not a patch.
3. **The stock refinement predicate is the wrong predicate.** [measured] Self-composition faked
   through `xdsl-tv` (both traces inside one function, returning `leak₁ - leak₂`, checked against a
   function returning `0`) reports **sat even for a constant-time kernel**: the encoding propagates
   *poison* from function arguments, so "always 0" fails to refine "literally 0". A control with no
   argument dependence is unsat, which pins the cause. Our driver must own its predicate: assume
   inputs non-poison, then compare the value components of the leakage traces.
   Reproduction in `prototypes/fcvd_ct/poc/`.
4. **Control flow does not exist** (upstream; see P3 below, which supplies it by if-conversion
   rather than by writing semantics). `SMTLowerer` rejects any region with more than one block
   [source: `lower_to_smt/smt_lowerer.py:48`], and there are no `cf`, `scf`, `affine` or `linalg`
   semantics anywhere in the tree [measured: grep]. The paper says as much — the five dialects are
   control-flow-free. Our own corpus is the opposite: across 118 `.mlir` files the op mix is `llvm`
   415, `cf` 74, `func` 66, `memref` 47, `scf` 27, `linalg` 8, `affine` 7. [measured] So
   "every `if` becomes a path condition, every loop bound becomes a predicate" is **the single
   largest cost item in this plan**, not a property we inherit.

A fifth point, and the one that took longest to notice: **the two halves of "safe" are separate
queries, and only one of them was being asked.** The leakage property cannot refute a value bug by
construction, upstream's value criterion is deliberately switched off inside our checkers (a constant
`false` refinement, which collapses upstream's assertion to the assumption we want), and for
structural templates nothing supplied it — `verify-pdl` takes only PDL patterns and `xdsl-tv` cannot
express a hole. Closed by P7 below.

A sixth point is about what may honestly be claimed at the end. `verify-pdl` proves a rewrite for all
programs; MLIR's `scf`→`cf`→`llvm` lowerings are C++ conversion patterns, not PDL rewrites.

*Revised by P3:* that is true of the implementation but does not bound what is provable. A lowering
has a **structural specification**, and the specification can be verified universally by making the
unknown code a hole (an uninterpreted function) — see P3. What remains genuinely per-program is the
link between the specification and the C++ pass that is supposed to implement it. So the deliverable
is: universal proofs for PDL rewrites (P5) *and* for structural lowering specifications (P3), plus
per-program translation validation tying real `mlir-opt` output to them (P1/P4). "The MLIR half is
fully verified for arbitrary code" still overstates it — the trusted assumptions are the leakage
model and the spec-implements-pass link — and we should keep saying so.

## 2. Design

Package `prototypes/fcvd_ct/` (uv, per repo conventions), importing `xdsl_smt` as a library. No fork
of xdsl-smt, no vendoring — see §5 on licensing.

**Labels.** Secrets are marked with an argument attribute on `func.func`, reusing the existing
convention from `prototypes/Staging_NI` (`stagingni.protected`) so one marking serves both tools.
Everything unmarked is public.

**Leakage as an output (`annotate-leakage` pass, MLIR→MLIR).** A pass that appends to the function's
results one value per observation, under a chosen leakage model:

| Observation | Emitted for | Threat covered |
|---|---|---|
| computed linear index / address | `memref.load`, `memref.store`, `llvm.getelementptr` | cache & address leaks |
| branch condition | `cf.cond_br`, `scf.if` (phase 3) | data-dependent control flow |
| trip count | `scf.for` bounds (phase 3) | loop-bound leaks |
| divisor / shift amount | `arith.divsi`, `remsi`, `shl`… | variable-latency instructions |
| allocation size + liveness | `memref.alloc`, `dealloc` | resource-leak obligation |

Doing this at MLIR level rather than inside xdsl-smt keeps the observation model reviewable, keeps us
off the upstream's internals, and makes the leakage model a swappable policy object — the same design
choice that made `leak_check`'s instruments comparable across axes.

**Self-composition driver (`fcvd-ct`).** Lower the annotated function to SMT twice with distinct
symbol names, then assert: public arguments equal ∧ initial memory equal ∧ *not* (leakage traces
equal), and `check-sat`. UNSAT = the kernel is constant-time under this leakage model; SAT = z3 hands
us the two secrets that separate the traces, and we print them as a counterexample. Memory-state
equality at exit gives the resource-leak obligation for free (§0).

**Verdicts.** `secure` / `insecure` + counterexample / `unknown` (unsupported op, timeout, or a
solver `unknown`) — `unknown` explicit and never silently folded into `secure`, matching the
discipline already enforced in `Staging_NI`.

## 3. Phases

Each phase ends with a falsifiable check and its own commit. P5 was pulled forward ahead of P1–P4;
the ordering below is otherwise the dependency order.

- **P0 — setup.** Clone, venv, upstream test suite, and the poison finding above. *Done, [measured].*
- **P1 — CT driver, straight-line.** `annotate-leakage` (addresses + variable-latency ops) +
  `fcvd-ct` + our own predicate. Check: a constant-index kernel → unsat; the same kernel with a
  secret-derived index → sat with a concrete counterexample; a table lookup `t[s & 3]` → sat.
- **P2 — corpus and negative controls.** Port the small kernels from `prototypes/mlir_leak`
  (`select`, `gather`, `cond`, `matvec`) down to the supported subset; both polarities of each; lit
  tests. Check: no kernel is silently `secure` because its ops were skipped — an unsupported op must
  produce `unknown`.
- **P3 — control flow, and lowerings as structural specifications. *Done.*** Tool
  `fcvd-ct-lowering`. Two corrections to what §1.4 above assumed:

  1. Control flow did not need new op semantics at all. `scf.if` and acyclic `cf` graphs are
     **if-converted** into guarded straight-line form (`predication.py`), which both models the
     control flow and sidesteps FCVD's single-block restriction. Loops are refused, not
     approximated.
  2. A lowering step *can* be verified universally without being a PDL rewrite. Written as a
     **structural specification** — `@source`/`@target` functions whose unknown parts are
     `fcvd.hole` operations, i.e. uninterpreted functions tied across the four programs by
     congruence axioms — a proof holds for every program the template can be instantiated with.
     This is strictly stronger quantification than P5: no dependence on which operations have
     semantics.

  The soundness-critical part is that observations are **guarded** by their path condition, since
  if-conversion evaluates both arms. Both mechanisms are pinned by mutation tests rather than
  asserted: comparing traces without guards makes `if_to_select_leaky` report *preserving*
  (a real leak hidden), and deleting the congruence axioms makes the *correct* lowering
  `scf_if_to_cf` fail rather than making the corpus pass. [measured]

  | template | lowering | verdict |
  |---|---|---|
  | `scf_if_to_cf` | `scf.if` → `cf.cond_br` + join block | ct-preserving (3 → 3) |
  | `if_to_select_pure` | branch over pure code → `arith.select` | ct-preserving (1 → 0) |
  | `select_to_cf` | `arith.select` → `cf.cond_br` | **ct-breaking** (0 → 1) |
  | `if_to_select_leaky` | branch over *leaking* code → `arith.select` | **ct-breaking** (3 → 2) |
  | `swapped_arms` | `scf.if` → `cf.cond_br`, arms exchanged | **ct-breaking** (3 → 3) |
  | `loop_unsupported` | anything with `scf.for` | unknown |

  `select_to_cf` is the static counterpart of the `select` kernels `mlir_leak` probes dynamically.
  The pure/leaky pair is the result worth keeping: **if-conversion is a hardening for pure code and
  introduces a leak for code that touches memory or divides**, because the untaken arm now executes
  — and the tool tells the two apart from the templates alone.

  Named trusted assumption: upstream's `-convert-scf-to-cf` is C++ (`IfLowering`, `ForLowering`, …
  on `rewriter.splitBlock`), not generated from a declarative spec — checked against llvm-project
  release/18.x [source]. So this proves the *specification* of the lowering, and "the C++ pattern
  implements this template" is assumed. That assumption is much smaller than trusting the pass, and
  P1/P4 discharge it per-program against real `mlir-opt` output.
- **P4 — differential across the lowering.** Run the property at each stage of a real pipeline
  (`scf`→`cf`→`llvm` via `mlir-opt`), and report the first stage at which a kernel that *was*
  constant-time stops being so. This is the actual research claim of the branch: not "this program is
  CT" but "this lowering step introduced the leak", and it is the static counterpart to the
  `sparse_tensor --sparsification` address leak the dynamic harness already found.
- **P5 — universal rewrite proofs. *Done* — done first, at the user's choice, since it is the only
  part that yields a "for all programs" statement.** `prototypes/fcvd_ct/`, tool `fcvd-ct-pdl`.
  The property proved for a rewrite S → T is

      forall x, x'.  L_S(x) = L_S(x')  ==>  L_T(x) = L_T(x')

  where L_X is the observation sequence of program X: *the rewrite may remove leakage, never add
  it*. Note it needs **no secret/public labelling** — the source program's own leakage is the
  declassification bound, which is exactly what lets the statement quantify over every program the
  pattern matches. Encoding: each side is lowered by upstream `pdl-to-smt` with the value-refinement
  criterion replaced by a constant `false`, which makes upstream's own assertion collapse to
  `preconditions /\ not ub` — precisely the assumption we want — and our obligation is appended on
  top of two independent instantiations.

  Measured [measured, 2026-07-28, z3 4.15.1, whole corpus in 5 s, 9 pytest cases green,
  ruff+ty clean]:

  | pattern | rewrite | `verify-pdl` (values) | `fcvd-ct-pdl` (leakage) |
  |---|---|---|---|
  | `mul_to_shl` | `x * 8 → x shl 3` | sound | ct-preserving (obs 0 → 0) |
  | `div_to_shift` | `x udiv 8 → x lshr 3` | sound | ct-preserving (obs 2 → 0) |
  | `rem_idempotent` | `(x urem 8) urem 8 → x urem 8` | sound | ct-preserving (obs 4 → 2) |
  | `shift_to_div` | `x lshr 3 → x udiv 8` | sound | **ct-breaking** (obs 0 → 2) |
  | `mask_to_rem` | `x and 7 → x urem 8` | sound | **ct-breaking** (obs 0 → 2) |
  | `div_swap_operand` | `x udiv 8 → y udiv 8` | unsound | ct-breaking (obs 2 → 2) |
  | `unsupported_float` | `x + y → y + x` on f32 | crashes | unknown |

  The result worth keeping: **two rewrites that upstream's verifier proves correct introduce a
  timing channel**, with a concrete counterexample (for `div_swap_operand`, z3 returns x = 0 in both
  runs and y = 0x00 vs 0xff). Controls: `div_swap_operand` rules out a checker that says "preserving"
  whenever the source leaks at all; `unsupported_float` must say `unknown`, and does — where
  upstream's `verify-pdl` instead dies with `ValueError: Cannot lower f32 type to SMT`.

  Scope, stated plainly: this covers **rewrites expressible in PDL**. MLIR's `scf`→`cf`→`llvm`
  lowerings are C++ conversion patterns and are not reachable this way; they need the per-program
  checker of P1–P4. The corpus exercises the variable-latency half of the leakage model only — the
  address rules are implemented but wait on P1, since address-shaped transformations are not what
  PDL patterns usually express.
- **P1/P2 — CT driver and corpus. *Done.*** `fcvd-ct`: the labelled self-composition of §2, with the
  three obligations of the plan's step 4 proved *separately* (plus `latency` for variable-latency
  instructions), so a verdict names the channel. Public inputs and the initial memory are shared SSA
  values rather than an assumption. Corpus `kernels/`, both polarities of each obligation; an
  unlabelled kernel is `unknown`, never `secure`. [measured, 2026-07-29]
- **P4 — differential across a lowering. *Partly done.*** Done per compiler and per stage, in
  `compiler-choice-circt-heir-onnx.agents.md`: for each of CIRCT, HEIR and onnx-mlir a chain of
  kernels transcribed from the pass source, with the verdict changing at the step that changes it —
  e.g. HEIR's `--convert-secret-extract-to-static-extract` closes `address` and opens `control`.
  Still missing: the IR should come from running the compiler, not from transcription.
- **The compiler layer — *done*, and the answer to "which compiler first".** `fcvd-ct-coverage`
  counts, for a compiler's own test corpus, how many operations are in form 0 / 1 / 2. HEIR 53.4 % of
  mentions translatable and 83 unproved operations, CIRCT 40.1 % and 188, onnx-mlir 33.6 % and 288.
  Findings and full scope in `compiler-choice-circt-heir-onnx.agents.md`.
- **P6 — integration.** A layer in `formal_verif/PIPELINE.md` next to A/B/C/D (this is the MLIR-level
  formal layer; binsec stays the binary-level one), a row in `run_all.sh`, and a results note.
  `prototypes/fcvd_ct/run_all.sh` exists; the `formal_verif` cross-link does not yet.
- **P7 — the equivalence half of the gate. *Done*, 2026-07-29.** "Safe" was stated from the start as
  functional equivalence *together with* resistance to timing attacks, and only the second half was
  being checked. For PDL rewrites the first half came from upstream `verify-pdl`, run beside ours; for
  **structural templates there was nothing at all**, because `verify-pdl` takes only PDL patterns and
  `xdsl-tv` cannot express a hole. The gap was not academic: the loop found it on Polygeist's
  `--canonicalize-for`, whose side condition is about functional equivalence, and recorded that the
  leakage property cannot falsify a value bug by construction.

  `structural.check_equivalence` closes it on the same machinery — same flattening, same holes, same
  congruence axioms — but relating what the two programs *return* and the memory they leave behind
  instead of their observation traces, under upstream's own criterion including UB polarity
  (`ub_source ∨ (¬ub_target ∧ agree)`). `check_template` requires both answers, `fcvd-ct-lowering`
  prints both, and `fcvd-ct-coverage` will not count a macro-template towards form 1 unless both hold
  (measured effect on all six descriptors: none, so nothing already claimed was resting on unchecked
  value behaviour).

  Two encoding choices, both found by a control that did *not* break, both pinned by mutation tests
  in `tests/test_gate.py` [measured, 2026-07-29]:

  1. the equivalence query asserts its **arguments are defined**. Without it a free poison bit
     reaches the guard CIRCT's `--convert-comb-to-arith` inserts (`divisor = (b == 0) ? 1 : b`), the
     target raises UB the source did not, and a correct pattern is refuted. Same family as the P0
     finding in §1.3, arriving through the UB clause instead of the value one.
  2. hole congruence relates the **whole** lowered value here, definedness included, unlike the
     leakage query — where comparing poison was removed in `6b4cf86` for its own good reason. Same
     code on the same input is either defined or not; leaving the outputs' markers free refuted the
     *correct* `--canonicalize-for` rewrite.

  | template | constant-time | equivalence |
  |---|---|---|
  | `polygeist/canonicalize_for_propagate_value` | ct-preserving (9 → 9) | equivalent, bounded |
  | `polygeist/canonicalize_for_propagate_moved_value` | ct-preserving (9 → 9) | **not-equivalent** |

  That pair is the deliverable: the mutation Polygeist refuses to perform passes the leakage half
  (correctly — a wrong answer leaks no more than a right one) and is refuted by the value half.

  Honest limits. **Most templates return nothing**, so their `equivalent` rests on the memory clause
  alone; the tool prints which, and giving templates results to return is the obvious next corpus
  task. **Memory is compared whole**, which is stronger than upstream's block-by-block refinement, so
  it can raise a false alarm on a lowering that reallocates — strict is the safe direction for a gate.
  **A hole does not touch memory**, so a template whose source models memory-touching code as a hole
  (`onnx_mlir/gather_to_krnl`) cannot be checked for equivalence at all, and its `not-equivalent` is a
  statement about the template, not about onnx-mlir. And the PDL corpus's value column is still
  upstream `verify-pdl` **run by hand** — not wired into `run_all.sh` or `pytest`, so unlike ours
  those verdicts are transcribed rather than re-derived.

## 4. What this does and does not buy us for the Jasmin question

The motivation for the branch is to close the MLIR half so effort can move to source- and
binary-level leakage (Jasmin). Being precise about the seam: after P1–P4 we can say "for *this*
kernel, *this* lowering pipeline preserved constant-time under *this* leakage model, machine-checked";
after P5, additionally "*this* rewrite preserves it for all programs it matches". Everything below
the last MLIR stage — instruction selection, register allocation, the actual x86 the CPU runs — stays
with layers A/B (binsec) and C/D (measurement), which already exist in `prototypes/formal_verif`. The
MLIR layer being green is not evidence about the binary, and the corpus should keep at least one
kernel that is CT in MLIR and provably not CT in the binary, as a live reminder.

## 5. Risks

- **`xdsl-smt` ships no LICENSE file** (checked at `dd30235`; `pyproject.toml` declares none either).
  [measured] We therefore **do not vendor or copy its code** into this MIT repo — it stays an
  external checkout, referenced as a dependency. Worth opening an upstream issue asking them to add
  one; until then, anything we might want to upstream is fine to write, but nothing of theirs comes
  in here.
- **Pinned deps.** xdsl 0.48.3 / z3 4.15.1 in a dedicated venv, isolated from `infoleak`/`ctverify`.
- **Solver blowup** on memory-heavy kernels: the array encoding is the usual suspect. Mitigation is
  the `-opt` pipeline plus keeping P1/P2 kernels small; if it bites, report `unknown`, never a
  hopeful `secure`.
- **Leakage model is a choice, not a truth.** Every verdict is relative to the table in §2. A
  `secure` verdict says nothing about port contention, speculation or cache geometry — the same
  caveat recorded for layers C/D.
