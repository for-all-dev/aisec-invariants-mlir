# Rev4 preflight and conformance workflow

This directory contains human-readable preflight fixtures. Each family/case
folder pairs one review-sized MLIR file with one strict `snapshot.yaml`. These
files are not frozen SPS artifacts, are not inputs to `NFConforms`, and cannot
produce a `ModelStatus`.

## Expected interpretation

The snapshot's `expect` value says what a reviewer should conclude at the
modeled MLIR boundary: a predicted violation, a negative control, a required
relational check, an unknown premise, a target risk, or shape-only evidence.
It routes future work without claiming that work has run. `sps: not-run` makes
that boundary explicit for every current case.

## What the current checks establish

`mlir-opt` plus `FileCheck` establishes only that a selected MLIR operation or
dataflow shape parses and survives the requested transforms. The unary scanner
may emit an `SPS-Harness-PreflightFinding-v2` review aid. Silence, a control
fixture, or a preflight finding does not imply any Rev4 diagnostic disposition
and cannot establish `Proved` or `Counterexample`.

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

## Snapshot contract

The sibling `snapshot.yaml` identifies itself as
`SPS-Harness-Fixture-Snapshot-v2` and records only the entry, same-family C provenance
in `c_evidence`, claim-relevant secret arguments, public observations, optional
release/audience allowance, expected fixture interpretation, short reason, and
SPS execution state. `c_evidence` is not a compilation-origin assertion.
Folder names supply family and case identity. Source hashes, capability
inventories, candidate bundle links, and expected reports are intentionally not
duplicated.

For current MLIR fixtures the execution state is always `sps: not-run`. The
snapshot checker rejects all other states until the production SPS parser and
verifier are integrated. At that point a non-`not-run` state will additionally
require the same case folder to contain `artifact.bc`,
`sps-manifest.sps.json`, and `sps-report.sps.json`; filenames alone never
establish that a run occurred.
