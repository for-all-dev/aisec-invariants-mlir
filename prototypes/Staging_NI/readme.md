# Staging Non-Interference Verification Pass for MLIR

## Overview

This project implements a **prototype MLIR analysis pass** for detecting **staging-time non-interference violations**.

The goal of the pass is to identify situations where **runtime-protected data influences compile-time (staging-time) decisions**, potentially leaking sensitive information through program structure rather than through explicit data values.

Unlike a full security analysis framework, this implementation is intentionally lightweight and avoids MLIR's DataFlow framework in order to demonstrate the core analysis algorithm in a clear and educational manner.

---

# Motivation

Modern compiler frameworks increasingly perform aggressive compile-time transformations based on program properties.

Operations such as

* tensor shape inspection
* loop bound computation
* affine address generation

may accidentally depend on protected runtime values.

For example,

```text
Protected Tensor
        │
        ▼
tensor.dim
        │
        ▼
loop bound
        │
        ▼
Compiler specialization
```

Even though the tensor values themselves are never revealed, the generated program structure may expose information about protected runtime data.

This class of leakage is called a **staging-time information flow**.

The objective of this pass is to detect these flows.

---

# Analysis Model

The pass implements a simple forward taint analysis over MLIR SSA values.

Two taint domains are maintained.

## Runtime Taint

Represents protected runtime data.

Examples include

* protected tensors
* protected memrefs
* values derived from protected runtime inputs

---

## Staging Taint

Represents compile-time values derived from runtime data.

Typical examples include

* tensor dimensions
* loop bounds
* affine indices

These values are not secret themselves, but they influence compiler decisions.

---

# Analysis Algorithm

The pass performs the following steps.

```
Protected Runtime Input
        │
        ▼
Runtime Taint
        │
        ▼
tensor.dim
        │
        ▼
Staging Taint
        │
        ▼
Arithmetic Propagation
        │
        ▼
Verification
```

---

## Phase 1 — Seed Runtime Taint

Protected function arguments are inserted into the runtime taint set.

Example

```mlir
func.func @foo(
    %A : tensor<?xf32> {stagingni.protected}
)
```

The value

```
%A
```

becomes runtime tainted.

---

## Phase 2 — Runtime → Staging Conversion

Whenever

```mlir
tensor.dim
```

is applied to a runtime-tainted tensor,

its result becomes staging tainted.

Example

```mlir
%dim = tensor.dim %A, %c0
```

Results in

```
%A
Runtime

↓

%dim
Staging
```

---

## Phase 3 — Runtime Propagation

Runtime taint propagates through SSA operations.

For example,

```mlir
%cast = tensor.cast %A
```

results in

```
%A

↓

tensor.cast

↓

%cast
```

remaining runtime tainted.

---

## Phase 4 — Staging Propagation

Staging taint propagates through **any** operation: if an operand carries it,
every result does.

This used to be gated on a whitelist of ten `arith` ops. A whitelist is a
silent-safe construct by design — an operation not on it consumed a tainted
value and produced a clean one, with no diagnostic, so `arith.shli`,
`affine.apply`, `arith.select` and every op in every dialect the list did not
enumerate were holes. Over-approximating instead follows the rule
`prototypes/initial`'s `VerifyNonInterference` already states: *if ANY operand
is tainted, ALL results become tainted — imprecise but sound.*

Taint also crosses the edges a purely operand→result rule cannot see:

* **memory** — a store of tainted data taints the destination buffer, so a
  later load from it is tainted (whole-buffer, index-insensitive);
* **regions** — a yielded value reaches the parent op's results and the
  loop-carried arguments it re-binds;
* **blocks** — branch successor operands reach the successor's block
  arguments (this is what keeps the analysis alive after `--convert-scf-to-cf`).

Because those edges run backwards as well as forwards, propagation **iterates
to a fixpoint** rather than relying on one walk order being correct.

Example

```mlir
%bound = arith.addi %dim, %c1
```

produces

```
%dim

↓

arith.addi

↓

%bound
```

where `%bound` is also staging tainted.

---

## Phase 5 — Verification

The pass reports violations whenever staging-tainted values influence compiler decisions.

Currently supported checks include

### Affine loops

```
affine.for
```

Checks

* lower bound
* upper bound

---

### SCF loops

```
scf.for
```

Checks

* lower bound
* upper bound
* step

---

### Memory accesses

```
affine.load    affine.store
memref.load    memref.store
```

Checks

* address indices

Both the affine and the plain `memref` forms. Checking only the affine ones
missed `mlir_leak`'s `idx_gather` — its canonical address-channel kernel,
measured leaking at every `-O` level — because it is written with
`memref.load`.

---

### Staging-time control flow

```
scf.if    scf.while    cf.cond_br
```

Checks

* `scf.if`'s branch condition
* `scf.while`'s condition (the operand of the `scf.condition` terminator in
  its "before" region)
* `cf.cond_br`'s condition — what the two above BECOME under the standard
  `--convert-scf-to-cf`. Checking only the `scf` forms meant going blind on
  the same program one lowering step later, which a differential run would
  have read as the leak having been removed.

A staging-tainted condition means the generated program's control-flow
*structure* itself depends on protected data — not just an address or a
loop trip count.

---

### Unmodeled constructs — UNKNOWN, not silently SAFE

A construct this analysis cannot correctly reason about is reported as
**UNKNOWN** (an `emitRemark`, not an error) whenever a tainted value reaches
it, instead of being silently treated as a taint barrier. Currently this
applies to:

* `secret.generic` region bodies (the HEIR Secret dialect is not in this
  project's dialect registry, so its ops can't be modeled; matched by
  operation name instead of being invisible to the walk);
* a **second handle onto a tainted buffer** (`memref.cast`/`subview`/`view`/
  `reinterpret_cast`/`collapse_shape`/`expand_shape`) — the memory model is
  per-SSA-value and models no aliasing, so a store through one handle is not
  seen through the other;
* a tainted value crossing a **call boundary** (`func.call`,
  `func.call_indirect`) — the analysis is intraprocedural.

Treating "cannot verify" as a distinct outcome from "verified safe" matters:
silently downgrading an unmodeled construct to SAFE is the same mistake as
reading a formal tool's "unknown" result as "secure" — see this monorepo's
`formal_verif/infoleak` FTZ layer, which exists specifically because
`binsec` is *silent*, not *secure*, on floating-point kernels.

Block arguments from loop induction variables and `scf.for`/`scf.while`
carried values (`iter_args` / the "before" region's arguments) are **not**
in this UNKNOWN list: those are resolvable, ordinary dataflow edges (a
tainted bound taints the induction variable it ranges over; a tainted
init value taints the corresponding region argument), and are propagated
outright rather than punted to UNKNOWN.

---

# Example

Input

```mlir
func.func @foo(
    %A : tensor<?xf32> {stagingni.protected}
) {

  %c0 = arith.constant 0 : index

  %dim = tensor.dim %A, %c0

  %c1 = arith.constant 1 : index

  %bound = arith.addi %dim, %c1

  affine.for %i = 0 to %bound {

  }

  return
}
```

Analysis

```
%A
Runtime

↓

tensor.dim

↓

%dim
Staging

↓

arith.addi

↓

%bound
Staging

↓

affine.for

↓

Violation
```

Output

```
Staging Non-Interference violation:
loop upper bound depends on protected runtime data
```

---

# Internal Architecture

```
runOnOperation()

│
├── seedRuntimeTaint()
│
├── propagate to FIXPOINT   (repeat until the taint sets stop growing;
│   │                        diagnostics suppressed during these rounds)
│   └── walk<PreOrder>(Operation*)
│           ├── visitTensorDim()                 // Runtime -> Staging (1)
│           ├── visitRuntimeToStagingCast()      // Runtime -> Staging (2)
│           ├── visitGenericRuntimePropagation()
│           ├── visitGenericStagingPropagation() // any op, no whitelist
│           ├── visitStore()                     // taint -> buffer
│           ├── visitRegionTerminator()          // yield -> results / iter_args
│           ├── visitBranchOperands()            // br args -> block args
│           ├── visitAffineFor() / visitScfFor() / visitScfWhile()
│           ├── visitUnmodeledAliasing()         // UNKNOWN
│           └── visitCall()                      // UNKNOWN
│
├── final walk, reporting = true   (emit each finding exactly once)
│       ├── visitAffineLoad/Store, visitAddressIndices   // address sinks
│       ├── visitScfIf / visitScfCondition / visitCondBranch  // control flow
│       └── visitSecretGeneric()                 // UNKNOWN
│
└── printSummary()   -> signalPassFailure() iff a VIOLATION was confirmed
```

# Design Decisions

This project intentionally avoids MLIR's DataFlow framework.

Reasons include

* simpler implementation
* easier to understand
* educational value
* explicit propagation logic
* minimal dependencies

The analysis instead performs a manual forward traversal over SSA operations using `func.walk()`.

It does, however, **iterate to a fixpoint**. Taint does not only flow
forward along SSA: it runs backwards around a loop's back edge (`scf.yield`
re-binds the `iter_args`) and outward from a region terminator onto the
parent op's results. No single traversal order is correct for all of those,
so the propagation rounds repeat until the taint sets stop growing, and
diagnostics are emitted only on a final walk once they are stable. The sets
only grow and are bounded by the number of SSA values, so this terminates.

The walk is pre-order because it converges in fewer rounds (a loop op seeds
its induction variable before its body is walked), not because correctness
depends on it.

---

# Current Limitations

This implementation is a **prototype** intended to demonstrate the core analysis algorithm.

The following features are intentionally not implemented, and any tainted
value reaching one of them is reported as **UNKNOWN** rather than silently
treated as safe (see "Unmodeled constructs" above) wherever this analysis
can detect that it happened:

* MLIR DataFlow Framework
* lattice-based analysis
* interprocedural analysis (a tainted value crossing a call is UNKNOWN)
* `secret.generic` region bodies (reported as UNKNOWN when a tainted operand
  reaches one — not modeled beyond that)
* alias analysis
* memory dependence analysis
* anything below the MLIR boundary: instruction selection and the LLVM
  backend's own transformations are invisible here, so a `clean` verdict is
  not a statement about the binary (see the `mask_select` row in
  "Cross-validation against measured ground truth")

Resolved (previously silently missed as false negatives, not merely
undocumented):

* block argument propagation for loop induction variables and
  `scf.for`/`scf.while` carried values (`iter_args` / "before"-region args)
  — these are ordinary resolvable dataflow edges, not unmodeled constructs
* `scf.for` `iter_args` propagation
* `scf.if`/`scf.while` condition checks (staging-time control flow) —
  previously not checked as a sink at all
* `cf.cond_br` conditions and branch-argument passing — the lowered forms of
  the above; without them the analysis went blind one standard pass later
* taint out of a region: yielded values now reach the parent op's results
  and loop-carried arguments, via **fixpoint iteration** (the propagation
  rounds repeat until the taint sets stop growing, so no single walk order
  has to be the right one)
* taint through memory (`memref`/`affine` store then load), and address
  sinks on the plain `memref.load`/`memref.store` forms, not just affine
* propagation through **any** operation, replacing a whitelist of ten
  `arith` ops that silently dropped taint everywhere else

Consequently, this pass should be viewed as a demonstration of staging-time taint analysis over MLIR SSA rather than a production-quality security verifier.

---

# Differential axis: `staging_ni_diff.py`

The checker answers "does this IR, as given, leak". On its own that cannot
attribute anything to a compilation step, which is the question
`../mlir_leak` exists to answer. `staging_ni_diff.py` asks it here too:
run the checker, lower with `mlir-opt`, run it again, compare.

```sh
python3 staging_ni_diff.py test/dynshape-cross-check.mlir
python3 staging_ni_diff.py ../mlir_leak/gather.mlir --protect 0 --pipelines P0 P1
```

Verdicts come from `../leak_check/differential.py` —
`verdict_two_builds`, the same quadrant `noninterference.py` uses — renamed
for this axis: `authored-and-survives`, `lowering-introduced`,
`lowering-removed`, `oblivious`. The pipeline table is imported from
`mlir_leak`'s `PIPELINES` rather than copied, so both prototypes sweep the
same compiler axis by construction.

**UNKNOWN is never folded into "no leak".** If the checker cannot model the
lowered form it reports `unknown-after`, not `lowering-removed`. The
distinction is the whole point of a differential: "the leak went away" and
"the analysis stopped being able to see it" produce the same `clean` reading
otherwise. That failure mode is not hypothetical — it happened twice while
building this, both times caught only by cross-checking against measured
results (see below), and both times the fix was a missing taint edge
(`cf.cond_br` conditions, then branch-argument passing) rather than a real
change in the program.

## Cross-validation against measured ground truth

`mlir_leak` compiles its kernels and measures them under Valgrind. Running
this checker over those same kernels is the only honest way to find out
whether its verdicts mean anything:

| kernel | `mlir_leak` measured @ -O0 | this checker | |
|---|---|---|---|
| `matvec` | oblivious | `oblivious` | agree |
| `cond_reduce` | LEAK (`taint:cf`) | `authored-and-survives` | agree |
| `idx_gather` | LEAK (`taint:addr`) | `authored-and-survives` | agree |
| `dynshape` | LEAK (`taint:cf`, `Dw`) | `authored-and-survives` | agree |
| `mask_select` | LEAK (`taint:cf`) | `oblivious` | **disagree** |

Reproduce:

```sh
python3 staging_ni_diff.py ../mlir_leak/{matvec,cond,gather,select,dynshape}.mlir \
        --protect 0 --pipelines P0 P1 P2
```

### The disagreement is a real blind spot, not a bug

`mask_select` is a branchless `arith.select` on a secret mask. At the MLIR
level it has no branch and no secret-derived address, so `oblivious` is the
correct answer *about the IR*. It leaks anyway, because the **LLVM `-O0`
instruction selector** lowers that select into a conditional branch
(`jne`) — a decision taken after MLIR is gone, which this checker cannot
observe even in principle. `mlir_leak`'s finding 1 documents the same thing
from the other side, including that `-O2/-O3` turn it branchless again.

So: **a `clean` verdict here is not a statement about the binary.** It means
no MLIR-level flow was found, under an over-approximating analysis, for the
constructs it models. Everything below MLIR — instruction selection,
register allocation, the backend's own transformations — is outside its
reach, and that region is exactly what `mlir_leak` measures. Neither tool
subsumes the other:

- this one covers **all inputs** structurally; a measurement covers only the
  two secret classes it actually runs;
- a measurement covers the **whole toolchain** down to the executed
  instructions; this one stops at the MLIR boundary.

# Relationship to `mlir_leak`

`../mlir_leak` measures the *same* leak class this pass targets — a
protected value's shape/extent driving a compile-time decision — but
dynamically: it lowers a kernel through several real MLIR pipelines and
LLVM `-O` levels, links it, and measures actual secret-dependence under
Valgrind. Where the two overlap (`mlir_leak/dynshape.mlir`'s buffer-extent
pattern, adapted here as `test/dynshape-cross-check.mlir`), this pass's
static prediction and `mlir_leak`'s measured result agree: both flag the
loop bound as leaking, on every lowering pipeline and every `-O` level
`mlir_leak` tried. This pass is the fast, no-compile, no-Valgrind
*predictor*; `mlir_leak` is the *ground truth* for the one property both
can express, and the only one of the two that can attribute a leak to a
*specific* lowering or optimization pass having introduced or removed it —
this pass has no lowering pipeline of its own to compare before/after, so
it cannot answer that question at all, only "does this IR, as given, leak."

---

# Relationship to HEIR

This implementation is **not** the HEIR staging analysis.

Instead, it is a simplified prototype that operates directly on ordinary MLIR SSA values annotated with

```
stagingni.protected
```

rather than on Secret dialect types such as

```
!secret.secret<...>
```

or region-based operations like

```
secret.generic
```

Its purpose is to illustrate the core ideas behind staging-time non-interference independently of HEIR's infrastructure.

---

# Future Work

Possible extensions include

* Secret dialect integration
* `secret.generic` region propagation
* MLIR DataFlow Framework implementation
* lattice-based taint domains
* fixpoint iteration
* block argument propagation
* interprocedural analysis
* richer affine expression analysis
* configurable security policies

---

# Educational Goals

This project is intended as a learning exercise in

* MLIR pass development
* SSA-based program analysis
* compiler security
* taint analysis
* visitor-based compiler traversals
* affine dialect analysis
* staging-time information flow
* forward data-flow reasoning

It favors readability and simplicity over completeness, making it suitable as a foundation for understanding more sophisticated compiler analyses.

