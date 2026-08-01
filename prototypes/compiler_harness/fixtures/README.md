# Checked-in LLVM-dialect MLIR shape fixtures

Files in this directory are preflight fixtures. They parse with ordinary MLIR,
pin review-sized compiler shapes with `FileCheck`, and intentionally make no
SPS `ModelStatus` claim. Generic `sps.*` attributes are candidate locators for
the unary scanner or future sidecar binding; IR self-annotation is never policy
authority.

## One readable snapshot per fixture

Every case lives at `fixtures/<family>/<case>/` and contains exactly one MLIR
file plus one `snapshot.yaml`. Family C provenance lives alongside the cases in
`fixtures/<family>/sources/`. The YAML is the only fixture boundary record:

```yaml
format_id: SPS-Harness-Fixture-Snapshot-v2
entry: dynamic_kv_length_bad

c_evidence:
  - ../sources/dynamic_kv_length_bad.c

secret:
  - {arg: 0, name: secret_length}

public:
  - {memory_at_arg: 2, name: public_allocation_count}
  - {memory_at_arg: 3, name: public_iteration_count}

expect: violation

because:
  - secret_length is stored into both public count fields

sps: not-run
```

The `format_id` literal keeps this fixture record disjoint from every SPS-owned
wire interface. Argument numbers are stable references; names are checked display aids. Public
items may also identify a public argument or one of the closed observations
`address`, `allocation-size`, `control`, `release-identity`, `return`, and
`timing`. `allowed` adds a minimal release or audience rule only when needed.
`finding: violation` is reserved for direct preflight flow that coexists with
an SPS binding refusal.

The expectation is one of `violation`, `no-violation`, `unknown`,
`relational-check`, `target-risk`, or `shape-only`. It describes fixture intent
at the modeled MLIR boundary, not a `ModelStatus`. All current fixtures say
`sps: not-run`.

`c/check_harness.py snapshots` validates strict YAML, the one-to-one
MLIR/snapshot layout, function arguments, pointer observations, boundary
equality for `bad`/`fixed` and `*-bad`/`*-fixed` pairs, and the absence of
authoritative result claims. It rejects aliases, anchors, explicit tags, merge
keys, duplicate keys, and unknown fields.

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

`PREFLIGHT FINDING` and `PREFLIGHT CONTROL` blocks are comments checked for
shape and adjacency. Their `preflight expectation` is a prototype review aid,
not a Rev4 diagnostic disposition or run-report result.

## Authority boundary

MLIR is convenient for authoring and reviewing a seed, but Rev4 analyzes frozen
canonical LLVM bitcode. Nine selected cases also contain a local `candidate/`
directory, where:

1. LLVM 17.0.6 currently produces candidate `artifact.bc`;
2. `artifact.ll` is derived from exactly those bytes for comparison;
3. prototype sidecars and a non-claimable workflow matcher are hash-bound,
   while `bundle-spec.json` records the case-local generation/binding recipe; and
4. a future LLVM 22.1.8 normal-form/freeze pipeline must replace the candidate
   capture before any theorem result is reportable.

`artifact.json.source_mlir_sha256` is capture-time provenance, not a live hash
pin on the readable case. Candidate validation still requires `source_mlir` to
name the sole sibling MLIR file and requires the current MLIR to lower to the
frozen `artifact.bc` bytes exactly. A comment- or annotation-only edit can pass
only when it is lowering-inert; lowering drift cannot be accepted through a
stale provenance hash.

Snapshot `c_evidence` paths bind provenance only. They do not assert that the
named C sources compile to the MLIR case or candidate bitcode.

Source and target timing examples need extra care. An argument marked as a
candidate secret for the unary scanner is not a coalition-derived Rev4 label.
A division or branchless select can look acceptable in a source model while
paired final-machine evidence remains open. Assembly checks therefore live
under `../p4-risk/`; they never turn a shape file into an SPS proof or
counterexample.

Those candidates remain quarantined by the `candidate/` boundary and do not
change `sps: not-run`. A future conformance `artifact.bc` must be deliberately frozen
and accompanied by canonical SPS inputs and an actual run report.

The current snapshot checker rejects every non-`not-run` state, even if files
with those names are present. Enabling another state requires wiring the
production parser and verifier into the harness; file presence alone is never
evidence that SPS ran.

See [the Rev4 workflow](REV4_PREFLIGHT_WORKFLOW.md) for that transition.
