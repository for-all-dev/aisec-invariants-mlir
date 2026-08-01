# Harness fixture tiers and SPS authority boundary

This harness uses two closed fixture tiers. The tier controls which claims a
passing test is allowed to make; directory placement or a suggestive filename
does not strengthen that claim.

## `PreflightV1`

A human preflight fixture contains one MLIR file and one `snapshot.yaml` under
`mlir/<family>/<case>/`. The snapshot says `sps: not-run` and records only the
claim-relevant boundary, expectation, and short reason. It may assert parsing,
shape, or the behavior of a non-authoritative scanner.

The nine LLVM-17 candidate bitcode pairs remain in the quarantined global
`artifacts/` suite while their compiler-pipeline tests are still useful. They
are not case-local `artifact.bc` files, are not frozen Rev4 artifacts, and do
not alter any snapshot's SPS state.

It must record the following claim boundary:

```json
{
  "nf_conforms": "NotEvaluated",
  "model_status": "NotComputed",
  "deployment_status": "NotComputed"
}
```

A preflight fixture must not contain a claimed verifier receipt, a witness in a
public status, a claimed `SPSRunReportV1`, or an assertion that scanner silence
proves noninterference. Candidate ABI data describes representation and alias
topology only; component roles and visibility authority belong to candidate
policy data, and Low/High is derived for each coalition.

## `ConformanceV1`

A conformance fixture is a snapshot of the actual Rev4 workflow. Its case
directory must contain, at minimum:

```text
artifact.bc
artifact.ll                         # optional derived review rendering
artifact-identity.sps.json          # exact ArtifactIdentityV1
identity-evidence.sps.json          # complete canonical preimage evidence
sps-manifest.sps.json               # exact SPSLLVMNFManifest
sps-report.sps.json                 # actual SPSRunReportV1
```

Any split-out policy, ABI, contract, placement, timing, observation, or release
file must be byte-equal to the corresponding manifest evidence. It is a review
projection, never a second authority.

The runner must bind identities, destroy the producer module, freshly parse
the exact `artifact.bc`, establish `NFConforms(T,I)`, construct the fixed query
schedule, retain each `AuditAll` raw result and `QueryDispositionV1`, validate
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

A matcher may use `ConstructedResultMatcherV1`,
`NotConstructedResultMatcherV1`, or a fresh-receipt matcher because it is not a
complete normative object. Such helper tags must never appear in verifier
output. Actual verifier tests validate compact canonical `SPSRunReportV1` JSON
with `tools/check_sps_run_report.py`.

## Promotion rule

Promotion from `PreflightV1` to `ConformanceV1` is a replacement, not a field
toggle. Recapture with the pinned Rev4 LLVM toolchain, create the complete
canonical manifest and identity evidence, run fresh-parse normal-form audit and
the exact verifier, and retain protected evidence for every issued receipt.
The candidate LLVM-17 bundles currently under `artifacts/` cannot be promoted
by changing their tier string.
