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

Staging taint propagates through arithmetic operations on index values.

Currently supported operations include

* arith.addi
* arith.subi
* arith.muli
* arith.divsi
* arith.divui
* arith.remsi
* arith.remui
* arith.index_cast
* arith.maxsi
* arith.minsi

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

### Affine memory accesses

```
affine.load
```

Checks

* address indices

---

```
affine.store
```

Checks

* address indices

---

### Staging-time control flow

```
scf.if
scf.while
```

Checks

* `scf.if`'s branch condition
* `scf.while`'s condition (the operand of the `scf.condition` terminator in
  its "before" region)

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
  operation name instead of being invisible to the walk).

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

├── walk<PreOrder>(Operation*)         // see Design Decisions: pre-order,
│       │                              // not the walk() default, is load-bearing
│       ├── visitTensorDim()                    // Runtime -> Staging (1)
│       │
│       ├── visitRuntimeToStagingCast()          // Runtime -> Staging (2):
│       │                                        // arith.index_cast of tainted data
│       ├── visitGenericRuntimePropagation()
│       │
│       ├── visitArithmeticStagingPropagation()
│       │
│       ├── visitAffineFor()            // + seeds induction var on tainted bound
│       │
│       ├── visitScfFor()               // + seeds induction var + iter_args
│       │
│       ├── visitScfWhile()             // + seeds "before" region args from inits
│       │
│       ├── visitAffineLoad()
│       │
│       ├── visitAffineStore()
│       │
│       ├── visitScfIf()                // staging-time control flow
│       │
│       ├── visitScfCondition()         // scf.while's condition
│       │
│       └── visitSecretGeneric()        // UNKNOWN, not silently SAFE
│
└── printSummary()
```

---

# Design Decisions

This project intentionally avoids MLIR's DataFlow framework.

Reasons include

* simpler implementation
* easier to understand
* educational value
* explicit propagation logic
* minimal dependencies

The analysis instead performs a manual forward traversal over SSA operations using `func.walk()`.

**The walk is explicitly pre-order** (`func.walk<WalkOrder::PreOrder>(...)`),
not `func.walk()`'s default (post-order — children visited before their
parent). Loop-bound-derived taint is seeded onto the induction
variable/`iter_args` by visiting the loop *op itself* (`visitAffineFor`/
`visitScfFor`/`visitScfWhile`); under the default post-order, every use of
those values *inside* the loop body would be checked before the loop op
seeds them, silently missing all of them. Pre-order visits the loop op
first, then its body, which is the order this analysis actually depends on.

---

# Current Limitations

This implementation is a **prototype** intended to demonstrate the core analysis algorithm.

The following features are intentionally not implemented, and any tainted
value reaching one of them is reported as **UNKNOWN** rather than silently
treated as safe (see "Unmodeled constructs" above) wherever this analysis
can detect that it happened:

* MLIR DataFlow Framework
* lattice-based analysis
* fixpoint iteration
* interprocedural analysis
* `secret.generic` region bodies (reported as UNKNOWN when a tainted operand
  reaches one — not modeled beyond that)
* alias analysis
* memory dependence analysis
* propagation of taint from a region's yielded values back onto its owning
  op's *results* (e.g. an `scf.if` whose *result* is a tainted value
  computed inside one branch is not currently tracked past the `scf.if` —
  only its branch *condition* is checked)

Resolved (previously silently missed as false negatives, not merely
undocumented):

* block argument propagation for loop induction variables and
  `scf.for`/`scf.while` carried values (`iter_args` / "before"-region args)
  — these are ordinary resolvable dataflow edges, not unmodeled constructs
* `scf.for` `iter_args` propagation
* `scf.if`/`scf.while` condition checks (staging-time control flow) —
  previously not checked as a sink at all

Consequently, this pass should be viewed as a demonstration of staging-time taint analysis over MLIR SSA rather than a production-quality security verifier.

---

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

