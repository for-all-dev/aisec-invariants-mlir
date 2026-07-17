# Validating dialect-specific opt passes: can mlir-tv target custom dialects?

Strategy note. Direction-setting for the project's static-verification arm (proposal W2 builds
on mlir-tv). Scope: feasibility comparison, no build. Tone/discipline follows
`../../prototypes/leak_check/PRINCIPLES.md` — claims are labelled **[source]** (from mlir-tv's
live source or a paper), **[measured]** (from our own runs), or **[inference]**.

## Executive summary

**Can mlir-tv be adapted to a custom dialect? Yes, but only by forking its C++ encoder — there is
no plugin API.** [source] For an *equivalence* check of a dialect-specific pass the cheap route is
to **lower both sides to the core dialects mlir-tv already models and validate there** (no fork).
For the project's actual target — **non-interference preservation** — neither cheap route suffices:
lowering erases the security labels, and the confidentiality property is a hyperproperty that plain
refinement can't express, so it needs a **forked encoder + self-composition in the VC generator**
(the W2 work). Meanwhile we *already* have a working, fork-free bug/leak finder for exactly these
passes — the `mlir_leak` dynamic differential harness, which found the `sparse_tensor
--sparsification` leak [measured]. Recommendation: use the dynamic harness as the immediate
empirical finder; scope the mlir-tv fork only once a concrete target dialect+pass and the
self-composition encoding are pinned.

## 1. Why dialect-specific passes are the right target

The premise — less-widely-used dialect passes are more bug-prone than core passes, so they are the
higher-yield verification target — is supported by the record:

- The mlir-tv line (*A Systematic Translation Validation Framework for MLIR-Based Compilers*, IJSEKE,
  doi 10.1142/S021819402450030X) reports **6 bugs, concentrated in `linalg`-dialect-specific
  passes**. [source]
- Regehr et al., **First-Class Verification Dialects for MLIR**, PLDI 2025
  (users.cs.utah.edu/~regehr/papers/pldi25.pdf, doi 10.1145/3729309) — a *different* architecture —
  found **5 miscompilation bugs in upstream MLIR** and verified a canonicalization pass + two
  dataflow transfer functions. [source]
- MLIR-focused fuzzers corroborate the "bugs cluster in less-audited transforms" picture: **DESIL**
  (OOPSLA'25) and **Ratte** (ASPLOS'25). [source]

Corollary for us: a translation-validation or differential-testing effort aimed at a
dialect-specific opt is aiming where the bugs actually are.

## 2. mlir-tv's extensibility reality (the core finding)

mlir-tv (`aqjune/mlir-tv`; Lee / Lopes / Regehr lineage, Alive2-style) is a **bounded, SMT-based
translation validator**: `mlir-tv <src.mlir> <tgt.mlir>` encodes both functions (which must share a
signature) into SMT and checks that the target **refines** the source (equivalence up to
UB/refinement). [source: README, `src/main.cpp`, `src/vcgen.cpp`]

**There is no plugin/registration API. Op semantics are a hardcoded C++ overload table.** [source]

- One `void encodeOp(State&, mlir::<dialect>::<Op>, bool)` per supported op in **`src/encode.cpp`**
  (~130 ops), dispatched by a hand-written macro chain `ENCODE(st, op, Ty, …)` in `encodeBlock`; an
  op matching no `ENCODE` line hits `throw UnsupportedException(&op)`.
- Supported surface (exhaustive, from the `encodeOp` signatures): **arith** (Add/Mul/Div/Sub/NegF,
  Add/Sub/Mul/XOrI, Cmp{F,I}, Constant\*, Ext/Trunc, Sh\*I, SIToFP, IndexCast, Select), **math**
  (AbsF/AbsI/Exp), **affine** (`affine.apply` *only*), **tensor**, **memref**, **linalg** (Generic,
  Matmul, Dot, Fill, Index, conv/pool variants), **tosa** (~28 ops), plus `bufferization`, `shape`,
  `sparse_tensor.convert`, `func`. **No `secret`/`aisec`/HEIR ops.**
- Supporting machinery a real extension touches: `abstractops.*` (abstract op/fp model), `value.*`
  (Tensor / MemRef / Float / Integer SMT value kinds), `memory.cpp` (memref block model), `state.*`
  (symbolic state), `vcgen.cpp` (refinement VC + the arg-type switch), `smt.*` (Z3/cvc5).

**Abstract float model — the standing soundness caveat.** fp ops are modelled as *uninterpreted
functions* with a few axioms, not bit-precise IEEE-754 (configurable `AbsLevelFpDot` FULLY_ABS vs
SUM_MUL, `AbsLevelFpCast`, `AbsFpAddSumEncoding`). [source: `abstractops.*`] So mlir-tv proves
equivalence *modulo the abstraction* (fp add treated as commutative-but-not-associative black box);
it cannot reason about exact rounding, and only F32/F64 are handled (F16 rejected). The flag
`--assign-random-to-unsupported-ops` lets validation skip unknown ops by assigning a fresh
unconstrained value — **explicitly unsound**, useful only when the unknown op is irrelevant to the
property, never when it *is* the thing under validation.

## 3. Three routes

### Route A — fork the encoder (teach mlir-tv the custom ops)
Add an `encodeOp` per custom op, plus new value/type kinds in `value.*` / `vcgen.cpp` if the dialect
introduces a new *type* (e.g. `!secret.secret<T>`), and register the dialect in `main.cpp` +
`CMakeLists.txt`. The type work is the heavier lift because refinement is defined structurally over
the existing value kinds. **The only route that reasons about the custom op's own semantics, and the
only one that can eventually reach the confidentiality property** — but that additionally requires
**self-composition in the VC generator** (a relational encoding: two copies of the program agreeing
on the public/low projection), which mlir-tv does not have. Cost: C++ fork + pinned LLVM + Z3
4.8.13 / cvc5 1.2.0. [source; inference on effort]

### Route B — lower both sides to core dialects, validate there
Run the custom pass; lower pre- and post-pass IR down to linalg/tensor/memref/arith; feed the two
lowered files to mlir-tv unchanged. **Cheap, no fork, and matches how mlir-tv is actually exercised**
(its tests validate core-dialect transforms, e.g. `conv2d-to-img2col`). [source] Limits: it validates
the *composite* `semantics ∘ lowering` vs `pass ∘ lowering`, so a bug in the lowering itself is in the
trusted base, not checked; and it **erases security labels** — `!secret.secret<T>` and taint info are
gone at plaintext linalg/arith level, so a refinement check on lowered IR sees **miscompilation
(integrity) only, not non-interference**. [inference, following the abstraction in §2]

### Route C — dynamic differential (the `mlir_leak` harness we already have)
Lower the dialect-specific opt to LLVM, run two secret/input classes under Valgrind (callgrind
retired-instruction/branch counts + memcheck **shadow-memory taint**), and diff. Already built and
validated; it found the `sparse_tensor --sparsification` address leak with no SMT and no fork —
`out[crd[i]]` leaked the sparsity pattern via the store address, caught by taint, invisible to the
count channel. [measured: `prototypes/mlir_leak/sparse/README.md`] **Detection, not proof**, and it
needs a runnable lowering — but it works on *any* dialect today and catches both
miscompilation-shaped and confidentiality-shaped divergences.

## 4. Decision framework

| | Route A (fork) | Route B (lower→core) | Route C (dynamic) |
|---|---|---|---|
| Guarantee | proves (static) | proves (static) | detects (runs) |
| Property reachable | integrity **and** confidentiality* | integrity only | integrity **and** confidentiality |
| Needs custom-op SMT semantics? | yes (write them) | no | no |
| Erases security labels? | no | **yes** | no |
| Setup cost | C++ fork + pinned LLVM/Z3/cvc5 | mlir-tv build only | **already built** |
| Blocks on | self-composition VC (W2) | nothing | a runnable lowering |

\*confidentiality via Route A only *after* self-composition + label propagation are added.

- **Integrity bug-hunting in a dialect-specific opt:** Route C now (cheap, working) or Route B (adds
  static proof, no fork). Route A is not justified for integrity alone.
- **The project's confidentiality / non-interference goal:** only Route A works — B erases labels, C
  detects-but-doesn't-prove — and it is gated on the self-composition VC work. This is the expensive,
  high-novelty path (and the proposal's W2).

**Recommendation (record, not prescribe):**
1. Use **Route C** as the immediate, low-cost finder over custom dialect-specific passes — it is the
   empirical arm and has already produced a result.
2. Use **Route B** as an intermediate to demonstrate the *integrity* half cheaply and to sanity-check
   that a pass's core-dialect lowering is equivalence-preserving before layering the security property.
3. Scope **Route A** (the static proof of non-interference preservation) only once a concrete target
   dialect+pass and the self-composition encoding are pinned — don't pay the fork + pinned-toolchain
   cost speculatively.

Honest caveat: even Route A inherits mlir-tv's **soundness-modulo-abstraction** (abstract fp,
core-dialect vocabulary), and every verdict here is scoped to specific pinned tool versions.

## 5. How this maps onto what exists in this repo

- `prototypes/initial/` is a **taint verifier pass** (`lib/Transforms/VerifyNonInterference.cpp`) over
  HEIR's `secret` dialect, introducing `aisec.protected` / `aisec.declassify` and reasoning over
  `secret.reveal` / `secret.generic`. It is **not** an SMT translation validator, and its property
  (non-interference) is a hyperproperty that plain refinement cannot express — which is exactly why W2
  proposes self-composition. Route A is where that pass's property would become a checked
  *preservation-across-lowering* guarantee.
- `prototypes/mlir_leak/` is Route C — the dynamic arm — and is the reason we can find dialect-specific
  opt leaks today without any of the above. The two are complementary: the harness *detects* a
  candidate leak fast; a forked mlir-tv would later *prove* (or refute) preservation for that pass.

## 6. Coverage landscape: the ML-compilation dialects are largely open

A blunt point that shapes the effort estimate: **existing static MLIR-verification tools barely touch
the ML altitude this project targets, and the one domain-specific dialect a state-of-the-art tool
covers is hardware, not ML.**

- **Regehr PLDI'25's five dialects are core + hardware, none ML-specific.** It defines semantics for
  `arith`, `func`, `builtin`, `memref`, and **`comb`** — quoted from the paper's contributions:
  "*a compilation transformation from key control-flow free MLIR dialects ('arith', 'func', 'builtin',
  'memref', and 'comb') to our semantic dialects*." [source: pldi25.pdf §Contributions] Four are
  generic core dialects; the only domain-specific one, **`comb`, is CIRCT's combinational-logic
  (hardware/EDA) dialect** — chosen because bit-precise stateless logic maps cleanly to SMT bitvectors
  (hence the `comb` known-bits/demanded-bits transfer functions). It is **orthogonal to ML
  compilation.** Also note all five are **control-flow-free** — a real scope limit vs. our
  data-dependent-control-flow target.
- **The closest ML-relevant static coverage is mlir-tv's `linalg`/`tensor`/`tosa`/`memref` encoding —
  but over *abstract* floats.** [source: `abstractops.*`] So even the best existing coverage of the
  ML stack reasons about tensor numerics coarsely (fp as uninterpreted functions, F32/F64 only), and
  says nothing about the `secret`/label information.
- **Framework ML dialects are entirely uncovered.** `torch` (torch-mlir), `stablehlo`/`mhlo`, IREE's
  `flow`/`stream`/`hal`, `mesh`, and HEIR's `secret` — none are in mlir-tv's op table or Regehr's five.

Consequence for scoping: the ML-dialect verification space is **open**, which is the proposal's
opportunity *and* its cost. There is no off-the-shelf semantics for the dialects that carry secret
weights; whichever route we take (fork mlir-tv's encoder, or write a Regehr-style lowering to a `smt`
semantic dialect) is **net-new semantics work on an ML/secret dialect**, not a matter of reusing
`comb`-style hardware coverage. This is additional weight on the recommendation to lead with the
dynamic harness (Route C), which needs no per-dialect semantics at all.

## Sources
- `aqjune/mlir-tv` — README, `src/encode.cpp`, `src/abstractops.*`, `src/value.*`, `src/vcgen.cpp`,
  `src/main.cpp` (github.com/aqjune/mlir-tv).
- Systematic TV Framework for MLIR — worldscientific.com/doi/abs/10.1142/S021819402450030X (6 linalg-pass bugs).
- Regehr et al., First-Class Verification Dialects for MLIR, PLDI'25 — users.cs.utah.edu/~regehr/papers/pldi25.pdf,
  doi 10.1145/3729309 (5 upstream miscompiles).
- DESIL (OOPSLA'25), Ratte (ASPLOS'25) — MLIR miscompilation fuzzing.
- Local: `prototypes/initial/lib/Transforms/VerifyNonInterference.cpp`, `prototypes/mlir_leak/README.md`,
  `prototypes/mlir_leak/sparse/README.md`, `docs/SPS-proj-proposal_compiler-confidentiality.pdf` (W2).
