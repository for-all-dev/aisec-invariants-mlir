# LLVM/MLIR confidentiality regression harness

This harness now separates five things that used to be conflated: compiler
shape, unary diagnostics, future Rev4 model results, final-binary risk, and
policy review. A green default run means the executable preflight checks pass;
it does **not** mean that SPS has returned `ModelStatus: Proved`.

The authoritative Rev4 theorem object will be frozen canonical LLVM bitcode.
The checked-in pairs here are deliberately weaker: LLVM 17.0.6 candidate
bitcode used to develop fixtures while the LLVM 22.1.8 normalizer, freeze
pipeline, exact relational verifier, and replay engine are still absent.

## Recommended reading paths

Do not learn this harness by reading its directories alphabetically. Start
with the evidence boundary, then follow one fixture family vertically. Within
each family, read `snapshot.yaml`, the sibling MLIR, the bad/fixed or control
comparison, the C provenance, any candidate bindings, and finally the linked
supporting tests. The snapshots and MLIR are preflight evidence; every current
snapshot remains `sps: not-run`.

### 1. Learn the evidence boundary

Read [the Rev4 preflight workflow](fixtures/REV4_PREFLIGHT_WORKFLOW.md), then
[the fixture format and authority boundary](fixtures/README.md). These explain
the different roles of C provenance, review-sized MLIR, candidate bitcode,
authoritative SPS inputs, and final-machine evidence.

### 2. Learn the core confidentiality concepts through preflight fixtures

Use [the common family-review workflow](FIXTURE_REVIEW_GUIDE.md#review-workflow-for-every-family),
then review these families in order:

1. [Rank 1: recipient, host, and release-audience authorization](FIXTURE_REVIEW_GUIDE.md#1-recipient-host-and-release-audience-authorization):
   [wrong-party plaintext](fixtures/wrong-party-plaintext/),
   [wrong-host FHE reveal](fixtures/wrong-host-fhe-reveal/), then
   [audience mismatch](fixtures/audience-mismatch/). This establishes that
   payload equality does not imply that the recipient, host, or coalition is
   authorized.
2. [Rank 2: release causality, sanitization, and explicit oracles](FIXTURE_REVIEW_GUIDE.md#2-release-causality-sanitization-and-explicit-oracles):
   [prefix-causal release](fixtures/prefix-causal-release/),
   [explicit error oracle](fixtures/explicit-error-oracle/), then
   [CKKS release](fixtures/ckks-release/). This adds what may be released, the
   required guard or sanitizer, and when that release becomes effective.

### 3. Review the real-world-derived ML-KEM case studies

These are faithful minimal reductions and compiler-pipeline regressions, not a
full Kyber or ML-KEM application test suite.

1. **KyberSlash1 and KyberSlash2.** Read the bad and fixed snapshots and MLIR
   under [KyberSlash1 `poly_tomsg`](fixtures/kyberslash1-poly-tomsg/) and
   [KyberSlash2 `poly_compress`](fixtures/kyberslash2-compress/), followed by
   each family's `sources/` directory. Then read
   [the LLVM code-generation test](integration/kyberslash-codegen.test) and
   [the C behavior-equivalence test](integration/equivalence.test). The direct
   secret-derived `udiv` is the simplest timing case: the repair preserves the
   tested result over coefficients `0..3328` while replacing division with
   reciprocal multiplication and shifting. The optional
   [unary latency diagnostic](diagnostic/latency.test) is scanner triage only,
   not theorem evidence or target-level timing closure.
2. **Clangover / ML-KEM.** Read the
   [source fixture](fixtures/clangover-poly-frommsg/source/), then the
   [pre-instruction-selection LLVM test](integration/clangover-frozen-ir-branchless.test),
   and then the [x86 code-generation test](p4-risk/clangover-x86-codegen.test).
   Only after seeing that evidence, compare the
   [bad target model](fixtures/clangover-poly-frommsg/lowered-bad/) and
   [fixed target model](fixtures/clangover-poly-frommsg/lowered-fixed/). These
   are hand-written models derived from the reviewed assembly, not the frozen
   LLVM module. This is the capstone because frozen LLVM can have
   secret-independent control while instruction selection creates a
   secret-dependent target branch. An LLVM model result and deployment
   evidence are therefore separate claims. The same
   [C behavior-equivalence test](integration/equivalence.test) exercises the
   reduced Clangover repair.

### 4. Complete the full review

Return to [the ranked review queue](FIXTURE_REVIEW_GUIDE.md#ranked-review-queue)
at rank 3 and continue through rank 12. Finish with the
[cross-cutting artifact review](FIXTURE_REVIEW_GUIDE.md#cross-cutting-artifact-review)
and the
[representation and coverage review](FIXTURE_REVIEW_GUIDE.md#cross-cutting-representation-and-coverage-review).
The application path above is an onboarding shortcut; it does not change the
guide's ranking or imply a severity order.

## Test strata

| Directory | What it checks | What it cannot claim |
| --- | --- | --- |
| `fixtures/` | Family-local MLIR/snapshot cases, C provenance under `sources/`, and optional case-local candidate bundles | Any `ModelStatus` |
| `diagnostic/` | The current unary scanner's five finding classes | Relational proof, replay, or proof from silence |
| `integration/candidate-bundles/` | Candidate `.bc`/derived `.ll` integrity and harness-namespaced matcher consistency | `NFConforms` or a current verifier report |
| `integration/` | C provenance, concrete witnesses, import, LLVM shape, candidate-bundle checks, the ungated NFv2 release-carrier structural contract, capability-gated NFv2 preservation/codegen contracts, invalid callable-marker negatives, the seven digest-pinned SPS lecture fixture contracts, executable MT-CM1/MT-CM4 countermodel witnesses, NF-A02/NF-A05/NF-CM02 surfaces, and retirement coverage | Whole-entry noninterference or a current `ModelStatus` |
| `p4-risk/` | Target-specific assembly/code-generation risk evidence | Model proof or closed deployment refinement |
| `sps/` | The capability-gated Rev4.1 V2 exact-verifier contract | No result without the exact V2 verifier and materialized bundle |
| `contracts/` | The digest-locked SPS Rev4.1 interface package, stage-report refusal boundary, cross-file `WFInputs` binding completeness, and typed replay/blocker aggregation | Any fixture `ModelStatus`; these validate interfaces and harness *expectations*, not verifier output |

Design-only coalition examples live under `examples/`; post-MVP authorization
and robust-declassification examples live under `examples/integrity/`. Neither
directory is discovered as a test suite.

## Fixture tiers

Every current checked-in semantic seed is preflight-only. Its human snapshot
says `sps: not-run`; it may preserve MLIR/LLVM shape or candidate policy
bindings, but it cannot assert `NFConforms` or a computed `ModelStatus`.

A future claim requires a new per-case Rev4.1 V2 materialization
containing frozen `artifact.bc`, exact `ArtifactIdentityV2` evidence, a
canonical `SPSLLVMNFManifestV2`, the complete derived query schedule,
protected-evidence bindings, and an `SPSRunReportV2`. Review-only `artifact.ll`
must always be derived from that frozen bitcode. Harness matcher records use
`SPS-Harness-*` format identifiers so they cannot be confused with normative
SPS objects.
The complete packaging and rematerialization contract is
[`contracts/FIXTURE_TIERS.md`](contracts/FIXTURE_TIERS.md).

Rev4.1 accepts only the V2 interface package. `CandidateOnly` fixture and
candidate labels identify nonclaimable harness evidence; they are not SPS
inputs and cannot produce a verifier result.

## Commands

Run from this directory:

```sh
make check             # every executable test, then an explicit SPS skip notice
make check-shape       # recursive MLIR/FileCheck plus snapshot validation
make check-diagnostic  # unary scanner tests; skipped unless SPS_SCAN is explicit
make check-candidates  # exact candidate .bc/.ll pairs and descriptor/oracle checks
make check-artifacts   # target alias for check-candidates
make check-integration # C provenance, witnesses, import, and LLVM shape
make check-p4-risk     # target-bound risk evidence only
make check-sps         # runs the feature-gated semantic suite (unsupported today)
make check-contracts   # WFInputs binding completeness and the aggregation collapse
make check-interfaces  # vendored Rev4.1 schemas, vectors, lock, and coupled drift
make list-tests        # discovery audit
make list-fixture-status # concise expect/sps/entry inventory for all 54 cases
```

Only the capability-probed V2 verifier path is active. Supplying a V2 report or
materialized directory cannot enable an SPS test.

The local runner uses `lit==17.0.6`. Create it explicitly if needed:

```sh
make bootstrap-lit
```

Tools default to `/opt/homebrew/opt/llvm/bin` and may be overridden:

```sh
make check LLVM_BIN=/path/to/llvm/bin
make check LIT=/path/to/llvm-lit
make check-diagnostic SPS_SCAN=/path/to/sps-scan
```

The seven mirrored lecture capture shapes are always verified against a
normalized digest recorded in `cases.json`, which needs no upstream corpus. To
additionally re-derive each `frozen.ll.sketch` digest from the real notes, run
the checker directly with `SPS_LECTURE_SOURCE` set:

```sh
SPS_LECTURE_SOURCE=/path/to/SPS/SPS_Lecture_Notes/artifacts \
  python3 tools/check_sps_lecture_cases.py --root .
```

Absent the variable it prints an explicit skip line; it never silently claims
the upstream check passed. The variable is deliberately not plumbed through
`make`: `integration/sps-lecture-source-drift-pin.test` asserts both the
skipped and the re-verified paths itself, using its own stand-in corpus.

`SPS_SCAN` has no automatic build-tree fallback. Requiring an explicit path
avoids silently running a stale, unversioned prototype binary. Missing optional
targets or tools produce `UNSUPPORTED`, not a fabricated success.

## SPS-owned Rev4.1 interfaces

SPS owns the Rev4.1 serialized records, unions, literals, reason classes, and
canonical field order under `SPS/interfaces/rev4.1/`. This harness consumes a
generated, digest-locked copy under `contracts/vendor/sps-rev4.1/`; it does not
maintain a second normative table. `contracts/sps-interface.lock.json` binds
the schema set, upstream revision, bundle digest, and registry digest.

Normal CI is offline and validates the vendored package and its canonical,
schema-invalid, byte-invalid, and cross-field vectors. Coupled CI sets
`SPS_INTERFACE_ROOT` to the upstream `SPS/interfaces/rev4.1` directory and
requires byte-for-byte equality. An intentional update uses:

```sh
python3 tools/sync_sps_interfaces.py \
  --source /path/to/SPS/interfaces/rev4.1 \
  --expected-source-revision SPS-Rev4.1-V2-2026-08-01
make check-interfaces SPS_INTERFACE_ROOT=/path/to/SPS/interfaces/rev4.1
```

The sync tool verifies the upstream manifest, complete digest closure, closed
schema references, canonical bytes, and requested source revision before it
atomically replaces the vendor directory. Cross-field mathematics remains in
cited validators under stable `XF-*` rule IDs.

Once a Rev4.1 run is materialized, `tools/check_sps_v2_bundle.py BUNDLE
--report REPORT` checks the six required bundle files (`artifact.bc`, artifact
identity, identity evidence, NF manifest, proof configuration, and aggregation
input) plus a separate `SPSRunReportV2`. It requires strict canonical interface
bytes, the vendored schemas and semantic rules, exact nested objects and digest
bindings, and exact bitcode bytes. It constructs and validates the closed
`AggregationDecisionV2` for every report arm, with the complete identity,
proof, and schedule bindings required for `CompletedV2`. This is a file-boundary
check; it does not run the verifier, establish `NFConforms`, or authenticate the
reported `ModelStatus`.

## Rev4.1 NFv2 release carrier

`SPS-LLVM-NF-v2` has one carrier: the zero-result, variadic-integer
`llvm.sps.release` intrinsic. Its operands are exactly the flattened
`ReleaseType` leaves in declared order and width. A `ReleaseId` is never an IR
operand; `ReleaseImplementationBindingV2.emitMarkerInstructionId` binds the
release-table entry to the stable intrinsic instruction ID.

The compiler-side contract requires `IntrHasSideEffects`, `IntrNoMem`,
`IntrNoDuplicate`, and `IntrNoMerge`, with no speculation. The intrinsic maps
one-for-one to `SPS_RELEASE` in MIR, remains present at the selected machine
capture boundaries, and is erased before MC emission without a call, symbol,
relocation, or instruction byte.

Lit does not enable this contract based on the intrinsic spelling or LLVM
version. Stock LLVM accepts an unknown `llvm.*` declaration as an ordinary
external call, so `lit.cfg.py` probes generated attributes, optimizer and
`SPSFinalWeaken_v2` survival before adding `sps-nfv2-intrinsic`. It separately
probes the MIR pseudo and final object before adding `sps-nfv2-codegen`. The
feature-gated tests remain `UNSUPPORTED` until those capabilities really exist.

The old callable wrapper, pinned wrapper, inline-assembly, metadata, and
store-only shapes remain executable as invalid-carrier negative evidence. Survival of
one of those forms does not establish an NFv2 carrier.

## The `.bc` / `.ll` ownership contract

Nine fixture cases contain a local `candidate/` bundle with both forms requested
for compiler-pipeline review. Each bundle is colocated with the MLIR/snapshot
case it describes:

- `artifact.bc` is the exact candidate byte sequence and the source of truth
  inside that pair;
- `artifact.ll` is generated by `llvm-dis artifact.bc`, never authored as an
  independent input;
- `artifact.json` is an explicitly nonnormative
  `SPS-Harness-Candidate-Artifact-v2` envelope with hashes for the bitcode, derived
  text, capture-time source MLIR, and every prototype sidecar. The source hash
  records the readable bytes used when the candidate was captured; it is not a
  live content pin for the evolving human-readable fixture;
- `policy.json`, `abi.json`, `contracts.json`, `release-table.json`, and
  `expected-report.json` are `SPS-Harness-Candidate-*` fixture descriptors and
  partial result matchers bound to the candidate bitcode hash. They are not
  canonical section-2 SPS interfaces.
- `bundle-spec.json` is the local generation and binding recipe for that one
  case; there is no global bundle registry. The sibling snapshot's
  `c_evidence` entries record provenance only, not a claim that those C files
  compile to the MLIR or `artifact.bc`.

`tools/artifact_bundle.py check` verifies the frozen-artifact and sidecar
hashes, the capture-source hash's SHA-256 shape, and the exact disassembly. It
also requires `source_mlir` to name the sole sibling MLIR file and lowers that
current file with the recorded producer toolchain: the result must still equal
`artifact.bc` byte for byte. Readable comments and harness annotations may
therefore evolve without rewriting a candidate only while lowering stays
identical; lowering-affecting drift is rejected. Regenerate intentionally:

```sh
python3 tools/artifact_bundle.py generate --llvm-bin /path/to/llvm/bin
```

These checks establish pair integrity, not Rev4 canonicality. A conformance
bundle must instead be produced by the pinned LLVM 22.1.8 late pipeline, carry
the complete normative `ArtifactIdentity` and canonical interfaces, destroy
and freshly reparse the frozen module, re-audit it, and feed the same bytes to
the fixed query/PONF/replay workflow and core instruction selection.

## Result contract

Rev4 has three independent result axes:

```text
ModelStatus       = Proved | Counterexample(receiptId)
                  | Unknown(PublicDispositionReasonV2)
DeploymentStatus  = Open(P4EvidenceProfileUnavailable) | Closed(P4EvidenceBundle)
PolicyReviewStatusV2 = Complete | Findings(finite set) | Incomplete(Reason)
```

The public counterexample constructor carries a fresh restricted-evidence
`receiptId`, never the witness itself.

There is one artifact-scoped `ModelStatus`. Per `(entry, coalition)` `AuditAll`
records are scheduled query results, not additional model statuses. A safety
`SAT` result remains `CandidateOnly`; only independent exact replay reaching
`Bad_A` permits `Counterexample(receiptId)`. Diagnostics, lints, source
filenames, and backend risk never directly determine the model result.

The files named `expected-report.json` are non-claimable harness matchers. Their
`expected` records separate `AuditAll` raw solver results, exact query
dispositions, replay prerequisites, and final status tags; they never fabricate
a public receipt. Each file records `CandidateOnly`, `PendingV2`, and
`claimable_from_checked_in_pair: false`. These candidate descriptors are useful
test intent, not replacements for canonical Rev4 policy, ABI, release,
contract, placement, or observation interfaces.

## Current semantic limitations

The current `sps-scan` propagates unary candidate Low/High dependence through SSA and
recognizes branch, public-sink, address, variable-latency-operation, and
allocation-size findings. It has no exact byte memory, complete alias topology,
prefix-causal release ledger, coalition products, witness replay, artifact
identity, or P4 refinement. A zero-finding result is therefore only silence.

The explicit coverage ledger at `contracts/rev4-conformance-matrix.json`
enumerates all `NF-A01`-`NF-A15` acceptance cases and `NF-CM01`-`NF-CM12`
countermodels. Rows marked `preflight-seed` or `infrastructure-seed` preserve a
useful shape; none is marked implemented.

## C and generated evidence

C reductions document provenance and support concrete two-run witnesses or
source-shape reproduction. Optimizers may erase the shape being illustrated,
and the VLA reduction may acquire stack-protector or volatile behavior outside
the Rev4 normal form. C is therefore motivation/preflight evidence unless an
exact conformant bitcode capture is separately audited.

`make -C c regen-mlir` writes imports under `build/mlir/`. Hand-minimized target
models remain visibly separate from target assembly in `p4-risk/`. Backend-only
branches, helper lowering, stack probes, and timing facts affect
deployment applicability or an explicitly future P4 evidence profile; they do
not retroactively change LLVM `ModelStatus`, and a risk observation is not by
itself a closed `DeploymentStatus` result.

## SPS lecture fixture contracts

The seven hand-authored teaching instances from
`SPS/SPS_Lecture_Notes/artifacts/` are mirrored under
`integration/Inputs/sps-lecture/`. Their integration tests assemble and
round-trip the LLVM capture shapes and check the invalid callable-marker model
and prefix order, and validate the complete three-coalition fixture matchers.
They are explicitly `CandidateOnly` and `claimable: false`; these checks do not
execute the relational semantics and their marker is an NFv2 negative.

The former V2 report tests have been removed. Rev4.1 teaching bundles must be
materialized anew against the V2 interfaces and `llvm.sps.release`; they cannot
reuse V2 identities.

The error-event fixture is deliberately split in two. The checked-in
`integration/Inputs/sps-error-events/future-conformance-contract.json` is a
nonclaimable `CandidateOnly` contract whose validator pins `DeclaredFailure`, the
mandatory verifier-UB error field, payload projection, and both exact event
orders. It is not an SPS report input. Rev4.1 requires a separately
materialized V2 bundle. The nine case-local candidate ABIs under
`fixtures/*/*/candidate/` are not V2 materialization inputs.
