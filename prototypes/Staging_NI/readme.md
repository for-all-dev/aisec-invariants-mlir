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

The pass consists of five logical components.

```
runOnOperation()

│

├── seedRuntimeTaint()

│

├── walk(Operation*)

│       │

│       ├── visitTensorDim()

│       │

│       ├── visitGenericRuntimePropagation()

│       │

│       ├── visitGenericStagingPropagation()

│       │

│       ├── visitAffineFor()

│       │

│       ├── visitScfFor()

│       │

│       ├── visitAffineLoad()

│       │

│       └── visitAffineStore()

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

---

# Current Limitations

This implementation is a **prototype** intended to demonstrate the core analysis algorithm.

The following features are intentionally not implemented.

* MLIR DataFlow Framework
* lattice-based analysis
* fixpoint iteration
* interprocedural analysis
* region-aware propagation
* `secret.generic` support
* block argument propagation
* `scf.for` `iter_args` propagation
* alias analysis
* memory dependence analysis
* control-flow-sensitive propagation

Consequently, this pass should be viewed as a demonstration of staging-time taint analysis over MLIR SSA rather than a production-quality security verifier.

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

