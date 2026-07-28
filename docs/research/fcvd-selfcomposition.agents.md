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
4. **Control flow does not exist.** `SMTLowerer` rejects any region with more than one block
   [source: `lower_to_smt/smt_lowerer.py:48`], and there are no `cf`, `scf`, `affine` or `linalg`
   semantics anywhere in the tree [measured: grep]. The paper says as much — the five dialects are
   control-flow-free. Our own corpus is the opposite: across 118 `.mlir` files the op mix is `llvm`
   415, `cf` 74, `func` 66, `memref` 47, `scf` 27, `linalg` 8, `affine` 7. [measured] So
   "every `if` becomes a path condition, every loop bound becomes a predicate" is **the single
   largest cost item in this plan**, not a property we inherit.

A fifth point is about what may honestly be claimed at the end. `verify-pdl` proves a rewrite for all
programs; MLIR's `scf`→`cf`→`llvm` lowerings are C++ conversion patterns, not PDL rewrites. So the
realistic deliverable is **per-program translation validation of CT preservation across a pipeline
run**, plus **universal proofs for the subset of rewrites we can express in PDL**. "The MLIR half is
fully verified for arbitrary code" is not something this architecture can deliver, and we should not
write it down.

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

Each phase ends with a falsifiable check and its own commit.

- **P0 — setup.** Clone, venv, upstream test suite, and the poison finding above. *Done, [measured].*
- **P1 — CT driver, straight-line.** `annotate-leakage` (addresses + variable-latency ops) +
  `fcvd-ct` + our own predicate. Check: a constant-index kernel → unsat; the same kernel with a
  secret-derived index → sat with a concrete counterexample; a table lookup `t[s & 3]` → sat.
- **P2 — corpus and negative controls.** Port the small kernels from `prototypes/mlir_leak`
  (`select`, `gather`, `cond`, `matvec`) down to the supported subset; both polarities of each; lit
  tests. Check: no kernel is silently `secure` because its ops were skipped — an unsupported op must
  produce `unknown`.
- **P3 — control flow.** `cf.cond_br` semantics (path merging over a bounded number of blocks) and
  `scf.if`/`scf.for` with statically known bounds via unrolling, registered from our package. Check:
  a secret-dependent `scf.if` → sat on the branch-condition observation; a public-bounded loop
  around a CT body → unsat. This is the phase most likely to slip; if block merging turns out to need
  upstream changes we contribute them rather than fork.
- **P4 — differential across the lowering.** Run the property at each stage of a real pipeline
  (`scf`→`cf`→`llvm` via `mlir-opt`), and report the first stage at which a kernel that *was*
  constant-time stops being so. This is the actual research claim of the branch: not "this program is
  CT" but "this lowering step introduced the leak", and it is the static counterpart to the
  `sparse_tensor --sparsification` address leak the dynamic harness already found.
- **P5 — universal rewrite proofs.** Express one such rewrite in PDL and extend `verify-pdl` with a
  CT-preservation criterion instead of value refinement, giving an "for all matching programs"
  statement for that rewrite. Scope honestly: it covers rewrites expressible in PDL, not C++
  conversion patterns.
- **P6 — integration.** A layer in `formal_verif/PIPELINE.md` next to A/B/C/D (this is the MLIR-level
  formal layer; binsec stays the binary-level one), a row in `run_all.sh`, and a results note.

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
