# Rev4 preflight and conformance workflow

This directory contains human-readable preflight fixtures. Each family/case
folder pairs one review-sized MLIR file with one strict `snapshot.yaml`. These
files are not frozen SPS artifacts, are not inputs to `NFConforms`, and cannot
produce a `ModelStatus`.

## Expected interpretation

Snapshot V3 gives every fixture one direct expected final judgment and sparse
typed properties for the intermediate endpoints that matter. It contains no
execution, capability, lineage, adapter, or materialization fields; lit owns
those operational details. The 74 nonclaimable expectations contain 32
`Proved`, 30 `Counterexample`, and 12 `Unknown` model results, all with
deployment `Open` and policy `Complete`. Relevant cases select closed SPS event
fields, never raw traces or protected evidence. Thirteen authenticate their
existing candidate expected-run sidecars through a compact `reference`; the
other 61 need no candidate artifact.

All 30 expected-`Counterexample` fixtures do, however, own a public synthetic
`counterexample-pair.yaml`. It makes the local oracle concrete at full ABI
width while remaining outside the authoritative result path. The snapshot
owns the bad-state/first-difference expectation; policy and ABI own labels and
representation; an exact SPS run alone may produce a restricted replay and
public receipt. The four bad precision reductions may independently replay
their digest-bound pair, but that executable-reference success has no
normative claim effect.

The eight precision-control snapshots add an `ExecutableReferenceOnly`
checkpoint over a hand-authored finite reduction. It is a regression bridge
between the fixture story and SPS relational machinery, not a third fixture
tier or a substitute for exact frozen-bitcode verification. Its reduced query
analogues and backend results therefore remain lowercase, nonclaimable
evidence.

## What the current checks establish

The checkpoint runner establishes only that a selected typed MLIR, diagnostic,
or backend endpoint matches its declared properties. The unary scanner may
emit an `SPS-Harness-PreflightFinding-v2` review aid. Silence, a control
fixture, or a preflight finding does not imply any Rev4 diagnostic disposition
and cannot establish `Proved` or `Counterexample`.

`finalize` is test bookkeeping: it checks that the checkpoints owned by one lit
test produced matching observations. It is not the fixture's final security
stage. The snapshot states the expected result now; a future `check-final`
invocation separately validates and compares an actual `SPSRunReportV2`.

Comments headed `PREFLIGHT FINDING` and `PREFLIGHT CONTROL` are executable
annotation-shape checks. Their final `preflight expectation` line describes
what this prototype should notice. These comments are neither policy authority
nor public run-report content.

The eventual Section-10 diagnostic runs once per `(entry, coalition)` over the
expanded LLVM entry and has exactly these dispositions:

```text
NotObservable
StaticallyDischarged(ruleId, premiseRefs)
DefiniteViolation(ruleId, premiseRefs, witnessRecipe)
RelationalRequired(reason)
Unknown(reason)
```

Even that diagnostic is non-authoritative: the fixed audit-all product query
and independent replay remain mandatory.

## Conformance boundary

A reportable Rev4 run starts from canonical interfaces and frozen bitcode, not
from an MLIR fixture:

```text
candidate C / MLIR shape
        │ CandidateOnly only
        ▼
candidate LLVM capture
        │ replace with the pinned canonical capture
        ▼
SPSLLVMNFManifestV2 + ArtifactIdentityEvidenceV2 + frozen artifact.bc
        │ reparse the hashed bytes, bind, normalize, and audit NFConforms
        ▼
fixed coalition-indexed query schedule + audit-all product
        │ solver validation and independent replay
        ▼
SPSRunReportV2
```

Only the conformance path may aggregate the public model result:

```text
ModelStatus = Proved
            | Counterexample(receiptId)
            | Unknown(PublicDispositionReasonV2)
```

`PolicyReviewStatus` and `DeploymentStatus` are independent report fields. A
source or target-model preflight fixture may identify a deployment risk, but it
cannot close final-machine observation refinement.

The vendored Rev4.1 registry currently defines only the `Open` deployment arm;
there is no `DeploymentStatusV2.Closed` constructor. End-to-end closure is
therefore unavailable until an upstream interface revision supplies and
validates that arm.

## Snapshot contract

The sibling `snapshot.yaml` identifies itself as
`SPS-Harness-Fixture-Snapshot-v3` and records the entry, same-family C
provenance, claim-relevant boundary, expected final axes/event selectors, and
sparse typed pipeline properties. The inventory derives pipeline ownership and
capabilities entirely from lit `RUN`/`REQUIRES` lines. `c_evidence` is
provenance, not a compilation-origin assertion.

Observations are nonclaimable YAML under the lit build root. Canonical SPS
interfaces and actual `SPSRunReportV2` values remain canonical JSON and are
validated by the vendored V2 interface package. File presence and a future
matcher alone never establish that a verifier ran.

When a real report becomes available, lit must expose the pinned verifier and
materialized Rev4.1 inputs. A separate `check-final --snapshot ... --report
...` path authenticates and validates that report before comparison with
`expect.final`. Packaging validation alone cannot produce an actual result.
