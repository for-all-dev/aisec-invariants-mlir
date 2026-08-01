# Harness fixture tiers and SPS authority boundary

This harness uses two closed fixture tiers. The tier controls which claims a
passing test is allowed to make; directory placement or a suggestive filename
does not strengthen that claim.

## `CandidateOnly`

A human preflight fixture contains one MLIR file and one `snapshot.yaml` with
`format_id: SPS-Harness-Fixture-Snapshot-v2` under
`fixtures/<family>/<case>/`. Family C evidence lives under the sibling
`fixtures/<family>/sources/` directory and records provenance; it is not a
claim that the C source compiles to the checked-in MLIR or candidate bitcode.
The snapshot says `sps: not-run` and records only the
claim-relevant boundary, expectation, and short reason. It may assert parsing,
shape, or the behavior of a non-authoritative scanner.

Nine cases contain a quarantined `candidate/` directory while their LLVM-17
compiler-pipeline tests remain useful. Each directory contains a local
`bundle-spec.json`, candidate bitcode and its derived review rendering, plus
prototype sidecars. These are not frozen Rev4 artifacts and do not alter the
case snapshot's SPS state.

It must record the following claim boundary:

```json
{
  "nf_conforms": "NotEvaluated",
  "model_status": "NotComputed",
  "deployment_status": "NotComputed"
}
```

A preflight fixture must not contain a claimed verifier receipt, a witness in a
public status, a claimed `SPSRunReportV2`, or an assertion that scanner silence
proves noninterference. Candidate ABI data describes representation and alias
topology only; component roles and visibility authority belong to candidate
policy data, and Low/High is derived for each coalition.

### Stage reports

When a preflight fixture records a completed partial check, it uses the complete
`SPS-Harness-Stage-Report-v2` object:

```json
{
  "formatId": "SPS-Harness-Stage-Report-v2",
  "fixtureTier": {"tag": "CandidateOnly"},
  "stageId": "ReleaseCarrierValidationV2",
  "completedChecks": ["InvalidCallableCarrierShapeCheckedV2"],
  "findings": [],
  "blockers": [],
  "claimable": false,
  "modelStatus": {"tag": "NotComputed"}
}
```

`completedChecks`, `findings`, and `blockers` are sorted, duplicate-free harness
identifier arrays. `NotComputed` is a harness sentinel, not a fourth
`ModelStatus` constructor. A stage report cannot carry `Proved`,
`Counterexample`, `Unknown`, a receipt, a witness, or a deployment result.
`tools/check_sps_stage_report.py` enforces this boundary for standalone vectors
and embedded high-value expectations.

## `ConformanceV2`

A conformance fixture is a snapshot of the actual Rev4 workflow. Its case
directory must contain, at minimum:

```text
artifact.bc
artifact.ll                         # optional derived review rendering
artifact-identity.sps.json          # exact ArtifactIdentityV2
identity-evidence.sps.json          # complete canonical preimage evidence
sps-manifest.sps.json               # exact SPSLLVMNFManifestV2
proof-configuration.sps.json        # exact ProofConfigurationV2
aggregation-input.sps.json          # exact AggregationInputV2
sps-report.sps.json                 # actual SPSRunReportV2
```

Any split-out policy, ABI, contract, placement, timing, observation, or release
file must be byte-equal to the corresponding manifest evidence. It is a review
projection, never a second authority.

The runner must bind identities, destroy the producer module, freshly parse
the exact `artifact.bc`, establish `NFConforms(T,I)`, derive the complete query
schedule, retain each `AuditAll` raw result and `QueryDispositionV2`, validate
candidate replays independently, aggregate one `ModelStatus`, and issue the
independent policy-review and deployment statuses.

## Harness matchers

Matcher objects are deliberately namespaced `SPS-Harness-*`. Within them,
copied SPS constructors retain their exact spellings and tagged shapes:

- query dispositions: `CandidateOnly`, `ValidatedExistentialWitness`,
  `ConstrainedOrUnexercised`, `Discharged`, or
  `Unknown({"reasonClassId": ...})`;
- model status: `Proved`, `Counterexample(receiptId)`, or
  `Unknown({"reasonClassId": ...})`;
- base-profile deployment status:
  `Open(P4EvidenceProfileUnavailable)`.

Harness-only matchers may use helper tags because they are explicitly
nonclaimable and never appear in verifier output. An active verifier report is
compact canonical `SPSRunReportV2` and is checked with
`tools/check_sps_v2_bundle.py` against the same materialized bundle given to
the verifier. Rev4.1 accepts only the V2 report interface.

Aggregation fixtures use the vendored `AggregationInputV2` record directly.
Its artifact-identity, proof-configuration, and query-schedule digests bind the
run inputs. Its `acceptedBadReplay` field is either `Option.None` or
`Option.Some(AcceptedBadReplayV2)`; the replay repeats those three bindings and
also carries its query ordinal, exact `QueryDescriptorV2`, first bad step/state
digest, and protected receipt. Complete `BlockerRecordV2` rows carry scope,
phase/schedule coordinates, the typed reason arm, and a restricted-detail
digest. An accepted replay may outrank only `ProofCompletion` blockers. A
`ReplayInvalidating` blocker makes an accepted token inconsistent, while a
`RunFinalization` blocker yields `ReportingFailedV2` outside `ModelStatus`.

## Required-module expectations

`tools/check_required_modules.py` models the Rev4.1 M19--M23 requiredness
matrix as `SPS-Harness-Required-Module-Evaluation-v2`. The model is a fixture
oracle, not an SPS report: every evaluation has `claimable:false` and
`modelStatus:{"tag":"NotComputed"}`.

- M19 candidate search is optional and discovery-only. Whether it is skipped
  or reports findings cannot close or block a proof gate.
- One healthy M20 Low/High diagnostic is required for every derived
  entry/coalition scope. Missing, malformed, stale, or incomplete health
  creates a vendored `BlockerRecordV2` with `ProofCompletion` scope and
  `DiagnosticHealthFailure`; conclusions and findings do not vote.
- Every M20 run that emits a diagnostic record needs a following M21
  timing-risk record. Failure to materialize that mandatory report/P4 record
  is represented by a `RunFinalization` / `EvidenceFinalizationFailure`
  blocker. Timing findings do not vote.
- M22 policy review is required only when a completed run is requested. Its
  `Complete`, `Findings`, or `Incomplete` status remains an independent axis;
  `Findings` can coexist with a proof axis that would yield `Proved` in an
  actual complete verifier run.
- M23 backend control delta is required only for an attempted deployment
  closure. Its absence leaves deployment evidence open without adding a model
  blocker.

The checker reads blocker scopes, public reasons, reporting reasons, and policy
status tags from `contracts/vendor/sps-rev4.1/interface-registry.json` through
`tools/sps_interfaces.py`. `contracts/required-modules.test` covers each row of
the matrix and the nonclaimability boundary.

## V2 rematerialization rule

A `CandidateOnly` candidate is never promoted or converted into
`ConformanceV2`. Create a new V2 materialization: recapture with the pinned
Rev4 LLVM toolchain, create the complete
canonical manifest and identity evidence, run fresh-parse normal-form audit and
the exact verifier, and retain protected evidence for every issued receipt.
The LLVM-17 bundles under `fixtures/*/*/candidate/` remain independent
nonclaimable evidence and cannot become V2 by changing their tier string.
