# Checked-in LLVM-dialect MLIR shape fixtures

Files in this directory are preflight fixtures. They parse with ordinary MLIR,
pin review-sized compiler shapes with `FileCheck`, and intentionally make no
SPS `ModelStatus` claim. Generic `sps.*` attributes are candidate locators for
the unary scanner or future sidecar binding; IR self-annotation is never policy
authority.

## Required header

Each `*.mlir` file has exactly one nonempty value for:

```mlir
// case: <human-readable case>
// entry: <function symbol without @>
// classification: <supported provenance class>
// c source: ../c/<existing file>.c
// upstream GitHub source: <immutable source or explicit none>
// upstream revision: <full revision or none>
// secret: <candidate secret inputs/components>
// public: <candidate public inputs/structure>
// diagnostic focus: <lower-kebab identifier>
// evidence boundary: <text naming L0 through L4>
```

`c/check_harness.py annotations` validates these fields, the C link, entry and
`CHECK-LABEL`, adjacent confidentiality error/repair comments, and the generated
`contracts/shape-fixtures.json` snapshot. It rejects legacy result headers such
as `expected outcome`, `observer/model`, `reason id`, and `outstanding
obligations`.

The snapshot records required future capabilities and any paired semantic
candidate bundle. It remains `scope: preflight-only` and
`model_status_authoritative: false`.

## Lit and FileCheck convention

The normal shape check is:

```mlir
// RUN: %mlir-opt %s | %FileCheck %s
```

Checks should bind the entry with `CHECK-LABEL`, capture only values needed for
the decisive dependence, and avoid SSA numbers or whole-module snapshots.
Canonicalization-sensitive fixtures may add a second prefix to ensure the
essential branch, address, allocation, or repair survives.

There are no `--verify-diagnostics` oracles here. The current scanner has its
own feature-gated tests under `../diagnostic/`; future exact model checks belong
under `../sps/` and must consume conformance bundles rather than MLIR text.

## Authority boundary

MLIR is convenient for authoring and reviewing a seed, but Rev4 analyzes frozen
canonical LLVM bitcode. Selected seeds map to `../artifacts/<case>/`, where:

1. LLVM 17.0.6 currently produces candidate `artifact.bc`;
2. `artifact.ll` is derived from exactly those bytes for comparison;
3. prototype sidecars and a non-claimable future oracle are hash-bound; and
4. a future LLVM 22.1.8 normal-form/freeze pipeline must replace the candidate
   capture before any theorem result is reportable.

Source and target timing examples need extra care. A High division or branchless
select can be clean in the fixed LLVM model while paired backend evidence is
still open. Assembly checks therefore live under `../p4-risk/`; they never turn
a shape file into an SPS proof or counterexample.
