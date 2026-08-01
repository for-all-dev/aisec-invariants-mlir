# LLVM/MLIR confidentiality regression harness

This harness now separates five things that used to be conflated: compiler
shape, unary diagnostics, future Rev4 model results, final-binary risk, and
policy review. A green default run means the executable preflight checks pass;
it does **not** mean that SPS has returned `ModelStatus: Proved`.

The authoritative Rev4 theorem object will be frozen canonical LLVM bitcode.
The checked-in pairs here are deliberately weaker: LLVM 17.0.6 candidate
bitcode used to develop fixtures while the LLVM 22.1.8 normalizer, freeze
pipeline, exact relational verifier, and replay engine are still absent.

For a priority-ordered, piece-by-piece manual review, use the
[fixture review guide](FIXTURE_REVIEW_GUIDE.md).

## Test strata

| Directory | What it checks | What it cannot claim |
| --- | --- | --- |
| `mlir/` | One MLIR file plus one readable boundary snapshot per family/case | Any `ModelStatus` |
| `diagnostic/` | The current unary scanner's five finding classes | Relational proof, replay, or proof from silence |
| `artifacts/` | Candidate `.bc`/derived `.ll` integrity and harness-namespaced matcher consistency | `NFConforms` or a current verifier report |
| `integration/` | C provenance, concrete witnesses, import, LLVM shape, the seven digest-pinned SPS lecture fixture contracts, executable MT-CM1/MT-CM4 countermodel witnesses, NF-A02/NF-A05/NF-CM02 normal-form surfaces, and the retirement-coverage observation | Whole-entry noninterference or a current `ModelStatus` |
| `p4-risk/` | Target-specific assembly/code-generation risk evidence | Model proof or closed deployment refinement |
| `sps/` | Future exact-verifier tests plus executable machine-interface contracts | Semantic tests are feature-gated `UNSUPPORTED` until the verifier and canonical LLVM 22.1.8 bundles exist |
| `contracts/` | Cross-file `WFInputs` binding completeness and the shared `ModelStatus` blocker-cardinality collapse | Any `ModelStatus`; these validate harness *expectations*, not verifier output |

Design-only coalition examples live under `examples/`; post-MVP authorization
and robust-declassification examples live under `examples/integrity/`. Neither
directory is discovered as a test suite.

## Fixture tiers

Every current checked-in semantic seed is preflight-only. Its human snapshot
says `sps: not-run`; it may preserve MLIR/LLVM shape or candidate policy
bindings, but it cannot assert `NFConforms` or a computed `ModelStatus`.

`ConformanceV1` is reserved for a future per-case directory containing frozen
`artifact.bc`, exact `ArtifactIdentityV1` identity evidence, a canonical
`SPSLLVMNFManifest`, the complete query schedule, protected-evidence bindings,
and an `SPSRunReportV1` matcher. Review-only `artifact.ll` must always be
derived from that frozen bitcode. Harness matcher records use `SPS-Harness-*`
format identifiers so they cannot be confused with normative SPS objects.
The complete packaging and promotion contract is
[`contracts/FIXTURE_TIERS.md`](contracts/FIXTURE_TIERS.md).

## Commands

Run from this directory:

```sh
make check             # every executable test, then an explicit SPS skip notice
make check-shape       # recursive MLIR/FileCheck plus snapshot validation
make check-diagnostic  # unary scanner tests; skipped unless SPS_SCAN is explicit
make check-artifacts   # exact candidate .bc/.ll pairs and descriptor/oracle checks
make check-integration # C provenance, witnesses, import, and LLVM shape
make check-p4-risk     # target-bound risk evidence only
make check-sps         # runs the feature-gated semantic suite (unsupported today)
make check-contracts   # WFInputs binding completeness and the aggregation collapse
make list-tests        # discovery audit
make list-fixture-status # concise expect/sps/entry inventory for all 53 cases
```

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

## The `.bc` / `.ll` ownership contract

The nine quarantined legacy candidate bundles contain both forms requested for
compiler-pipeline review. They remain under global `artifacts/` and are never
copied into a human case folder:

- `artifact.bc` is the exact candidate byte sequence and the source of truth
  inside that pair;
- `artifact.ll` is generated by `llvm-dis artifact.bc`, never authored as an
  independent input;
- `artifact.json` is an explicitly nonnormative
  `SPS-Harness-Candidate-Artifact-v1` envelope with hashes for the bitcode, derived
  text, source MLIR, and every prototype sidecar;
- `policy.json`, `abi.json`, `contracts.json`, `release-table.json`, and
  `expected-report.json` are `SPS-Harness-Candidate-*` fixture descriptors and
  partial result matchers bound to the candidate bitcode hash. They are not
  canonical section-2 SPS interfaces.

`tools/artifact_bundle.py check` verifies the hashes, reproduces the exact
disassembly, and verifies that the checked-in `.ll` reassembles to the exact
`.bc` bytes with the recorded producer toolchain. Regenerate intentionally:

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
                  | Unknown(PublicDispositionReasonV1)
DeploymentStatus  = Open(P4EvidenceProfileUnavailable) | Closed(P4EvidenceBundle)
PolicyReviewStatus = Complete | Findings(finite set) | Incomplete(Reason)
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
a public receipt. Each file records `PreflightV1`, `PendingV1`, and
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
round-trip the LLVM capture shapes, check the current reserved release-marker
model and prefix order, and validate the complete three-coalition fixture
matchers. They are explicitly `PreflightV1` and `claimable: false`; these checks do not execute
the relational semantics.

Matching tests under `sps/` state the future exact semantic expectations and
validate the canonical machine `SPSRunReportV1`, rather than human-rendered
verdict text.
They use `REQUIRES: sps-verifier, llvm-22.1.8,
sps-teaching-materialized`, so the current harness reports them as
`UNSUPPORTED`, never as passing or expected failures.

The error-event fixture is deliberately split in two. The checked-in
`integration/Inputs/sps-error-events/future-conformance-contract.json` is a
nonclaimable `PreflightV1` contract whose validator pins `DeclaredFailure`, the
mandatory verifier-UB error field, payload projection, and both exact event
orders. `sps/error-events-conformance.test` is the future semantic arm; set
`SPS_ERROR_MATERIALIZED` to the real `ConformanceV1` case directory only after
LLVM 22.1.8 materialization and the exact verifier exist. The nine legacy
candidate ABIs under `artifacts/` are unchanged and are not promotion inputs.
