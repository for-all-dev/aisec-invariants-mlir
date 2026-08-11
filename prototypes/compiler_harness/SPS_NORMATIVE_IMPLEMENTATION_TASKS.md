# SPS normative pipeline implementation tasks

This document tracks the work required to turn the current compiler-harness
fixtures into inputs for an actual SPS Rev4.1 analysis. The present fixtures
remain `CandidateOnly`: their snapshots state expected test positions, but no
checked-in expectation establishes `NFConforms`, constructs a normative PONF,
or supplies an `SPSRunReportV2`.

The implementation must generate actual evidence without reading
`snapshot.yaml`. Only after an SPS run is complete may the harness compare its
report with the snapshot expectation.

```text
frozen artifact.bc
        |
        v
ArtifactIdentityV2 and bound inputs
        |
        v
recomputed NFConforms(T,I)
        |
        v
BuildPONF_v2 for every required query
        |
        v
deterministic SMT lowering and solving
        |
        v
independent candidate validation and exact replay
        |
        v
normative aggregation and SPSRunReportV2
        |
        v
harness comparison with snapshot.yaml
```

## Existing foundations

- [x] Separate fixture expectations from expectation-blind observations.
- [x] Keep current fixtures explicitly nonclaimable and test-only.
- [x] Store authoritative policy, ABI, release, alias, and contract meaning
  outside review MLIR.
- [x] Give expected counterexamples concrete synthetic left/right pairs without
  representing those pairs as solver witnesses.
- [x] Vendor and validate the Rev4.1 interface schemas and canonical vectors.
- [x] Test report aggregation rules with synthetic interface values.
- [ ] Produce an actual artifact-scoped `ModelStatusV2` from frozen bitcode.

The checked items are interface and harness foundations. They do not imply that
the exact SPS verifier exists.

## Milestone 0: choose the first vertical slice

- [ ] Select one scalar, integer-only fixture with no loop, recursion, indirect
  call, release, floating point, or vector operation.
- [ ] Prefer a direct public-output counterexample so the first slice exercises
  SAT-model validation and replay.
- [ ] Select a closely related safe/control fixture to exercise an `UNSAT`
  `AuditAll` query.
- [ ] Record the exact subset of the LLVM profile required by these two cases.
- [ ] Keep every other fixture `CandidateOnly` while this slice is developed.

The first milestone is not “support all fixtures.” It is one independently
materialized bad/control pair that exercises the complete pipeline.

## Milestone 1: exact bitcode materialization and identity

- [ ] Pin the exact LLVM 22.1.8 build and every relevant tool binary digest.
- [ ] Pin the target configuration, data layout, compiler pipeline, options,
  and freeze coordinate.
- [ ] Generate canonical `artifact.bc`; derive `artifact.ll` from those exact
  bytes for review only.
- [ ] Record the complete pass trace and reject mutation after the freeze
  coordinate.
- [ ] Destroy the producer module and freshly parse the frozen bitcode before
  analysis.
- [ ] Implement canonical bitcode serialization and recompute
  `canonicalBitcodeHash`.
- [ ] Materialize `ArtifactIdentityV2` and complete
  `ArtifactIdentityEvidenceV2` preimages.
- [ ] Generate the stable-IR binding table that maps policy/ABI/site IDs to the
  final LLVM artifact. Do not treat MLIR locators as final authority.
- [ ] Bind policy, ABI, release table, contracts, placement, alias topology,
  public bounds, proof configuration, and all other identity inputs by their
  canonical digests.
- [ ] Add negative tests for changed bitcode bytes, stale hashes, changed
  target options, missing bindings, and post-freeze mutation.

Acceptance condition: a clean rerun produces byte-identical canonical bitcode
and identity material, while every identity mutation is rejected before model
analysis.

## Milestone 2: implement and recompute `NFConforms(T,I)`

- [ ] Implement the closed LLVM profile dispatcher and exhaustive residual
  inventory. Every instruction, type, attribute, intrinsic, flag, metadata
  item, call, and global must be classified.
- [ ] Validate the exact call graph, supported direct-call expansion, and call
  bounds.
- [ ] Validate canonical loop structure, public `BoundId` bindings, semantic
  bounds, and separate engine caps.
- [ ] Validate byte-memory representation, allocation sizes, address spaces,
  ABI roots, public alias topology, initialization surfaces, and output
  closure.
- [ ] Validate release carriers, stable site bindings, placement, event
  inventory, and observation bindings.
- [ ] Reject unsupported floating-point arithmetic, vectors, poison flags,
  unclassified annotations, and every other unsupported residual construct.
- [ ] Distinguish failures that prevent identity binding
  (`ConfigurationRejectedV2`) from profile/model blockers that produce
  `Unknown` after identity is bound.
- [ ] Emit an `NFConformanceAuditRecord` for diagnostics, but always recompute
  the predicate; never accept a stored `nf_conforms: true` assertion.
- [ ] Add one negative fixture for each implemented conformance rule and verify
  that no audit result can be suppressed or downgraded to a warning.

Acceptance condition: the first exact artifacts either satisfy every applicable
Rev4.1 NF premise or fail closed with a stable reason. Scanner silence and
candidate-bundle integrity are never accepted as `NFConforms`.

## Milestone 3: canonical PONF construction and SMT lowering

- [ ] Parse and validate the complete identity-bound `BoundInputsV2`.
- [ ] Derive `PublicQueryScheduleV2`; do not obtain the query list from fixture
  expectations.
- [ ] Implement `BuildPONF_v2` independently for each concrete entry,
  coalition, and required query.
- [ ] Encode both executions, individual admission, initial `LowEq`, permitted
  High variation, exact choices, and prefix-causal release-ledger state.
- [ ] Encode guarded SSA, exact byte memory and initialization, allocation
  identity, alias realizations, calls, and bounded loop copies required by the
  supported slice.
- [ ] Encode every applicable `Bad_A` disjunct. Never assume equal branches,
  successors, calls, statuses, or observations merely to reduce solver cost.
- [ ] Canonically serialize `SPS-PONF-v2` and compute its digest.
- [ ] Implement deterministic `LowerPONFToSMT_v2` and digest the exact canonical
  SMT-LIB bytes sent to the solver.
- [ ] Pin solver name, version, binary digest, options, and resource limits.
- [ ] Emit one `PONFResultArtifactV2` for every scheduled query, including
  `UNKNOWN` and not-constructed dispositions.
- [ ] Add determinism tests for PONF bytes, SMT-LIB bytes, query order, and
  result bindings.
- [ ] Add mutation tests proving that missing constraints, extra hidden
  constraints, digest drift, or a different lowering version are rejected.

Acceptance condition: repeated clean runs construct byte-identical PONF and
SMT inputs for the same artifact/configuration, and every query result binds to
those exact bytes.

## Milestone 4: candidate validation and exact replay

- [ ] Treat every SAT assignment as a candidate, never as a counterexample by
  itself.
- [ ] Decode the complete left/right initial states and choices from a solver
  model.
- [ ] Independently recheck both `Admitted` predicates, initial `LowEq`, High
  variation where required, ABI representation, and alias topology.
- [ ] Replay both lanes with the exact Rev4.1 transition semantics through the
  claimed first bad transition.
- [ ] Recompute the selected observation projection and `Bad_A` disjunct from
  replayed states rather than candidate fields.
- [ ] Implement `ReplayCovered_A` checks, including exact artifact identity,
  supported consumed prefix, first-bad-state minimality, and query binding.
- [ ] Accept candidates from SMT, a directed falsifier, differential tests, or
  authored fixture pairs through the same validation entry point.
- [ ] Store raw models, inputs, traces, memory, choices, and first-failure
  details only in authenticated restricted evidence.
- [ ] Return only a random protected-evidence receipt in public records.
- [ ] Add tests for malformed models, non-admitted inputs, non-Low-equal pairs,
  stale artifacts, wrong paths, wrong first differences, and replay failures.

Acceptance condition: a public `Counterexample(receiptId)` is possible only
when independent exact replay reaches `Bad_A`. A rejected or unreplayed
candidate cannot become a counterexample.

## Milestone 5: normative aggregation and reporting

- [ ] Require one result row for every entry, coalition, and query in the
  derived public schedule.
- [ ] Build `AggregationInputV2` from actual query dispositions, an optional
  accepted replay, typed blockers, and the independently computed
  `allRequiredGatesClosed` fact.
- [ ] Implement the Rev4.1 aggregation priority exactly:
  `RunFinalization` failure, accepted bad replay, remaining model blockers,
  then `Proved` only when every required gate is closed.
- [ ] Emit the closed `SPSRunReportV2` union:
  `ConfigurationRejectedV2`, `ReportingFailedV2`, or `CompletedV2`.
- [ ] For `CompletedV2`, emit a canonical `SPSPublicReportV2` containing the
  artifact/proof digests, complete query schedule and results, fixed preflight
  summaries, `ModelStatusV2`, `DeploymentStatusV2`, policy-review status and
  report, one run-evidence receipt, and the status-noninterference constant.
- [ ] Keep model, deployment, and policy-review statuses independent.
- [ ] Exclude raw witnesses, solver models, traces, secret-selected locations,
  blocker details, and content-derived witness digests from the public report.
- [ ] Validate the report structurally, canonically, and semantically against
  the same identity evidence and aggregation input used by the run.
- [ ] Add end-to-end report tests for `Proved`, `Counterexample`, `Unknown`,
  configuration rejection, and reporting failure.

Acceptance condition: the normative report is generated entirely from actual
bound run evidence and validates against the Rev4.1 interface package. No
snapshot value is copied into it.

## Milestone 6: harness integration and fixture promotion

- [ ] Add a capability-gated command that materializes one exact conformance
  bundle in a temporary directory.
- [ ] Add `check-final` behavior that validates the actual
  `SPSRunReportV2` first and only then compares its three public status axes
  with `snapshot.yaml`.
- [ ] Require expectation-blind producers: compiler, conformance audit, PONF
  builder, solver, replay validator, and aggregator receive no snapshot path or
  bytes.
- [ ] Verify every cross-file digest and reject stale or mixed-run files.
- [ ] Reproduce the complete bundle from a clean build and compare canonical
  bytes/digests.
- [ ] Promote only the completed vertical-slice fixtures to `ConformanceV2`.
- [ ] Keep all remaining fixtures `CandidateOnly` and continue using them as
  teaching, shape, binding, scanner, or semantic-reference regressions.
- [ ] Expand the supported LLVM fragment and promote additional fixtures one
  family at a time.

A promoted case contains, at minimum:

```text
artifact.bc
artifact.ll                         # derived review rendering
artifact-identity.sps.json
identity-evidence.sps.json
sps-manifest.sps.json
proof-configuration.sps.json
aggregation-input.sps.json
sps-report.sps.json
```

PONF objects, exact SMT-LIB inputs, solver models, and replay traces follow the
public/restricted evidence rules of the normative interfaces; they must not be
placed casually in public fixture files.

## Definition of done for the first conformance fixture

- [ ] A clean run begins with frozen bitcode and does not consume the snapshot.
- [ ] Artifact identity and all canonical preimages validate.
- [ ] `NFConforms(T,I)` is freshly recomputed and holds.
- [ ] The complete required query schedule is derived and executed.
- [ ] Every PONF and exact SMT formula has a reproducible digest.
- [ ] Every SAT candidate is independently validated; a reported bad witness
  is exactly replayed.
- [ ] Aggregation produces one valid `SPSRunReportV2`.
- [ ] The harness independently compares that report with the snapshot.
- [ ] Tampering with bitcode, bindings, PONF, SMT, receipts, replay, or report
  is detected.
- [ ] A reviewer can distinguish public report material from restricted
  witness evidence and from nonclaimable fixture expectations.

## Explicit non-goals for this work

- Proving that C or MLIR was compiled correctly into the frozen LLVM artifact.
- Closing target-machine, speculative-execution, or physical timing claims.
- Promoting every existing fixture before one complete vertical slice works.
- Treating a hand-authored expected report, synthetic pair, scanner finding,
  schema-valid object, or audit log as a normative SPS result.
