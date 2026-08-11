# Checked-in LLVM-dialect MLIR shape fixtures

Files in this directory are preflight fixtures. They parse with ordinary MLIR,
pin review-sized compiler shapes with typed Snapshot V3 matchers, and
intentionally make no SPS `ModelStatus` claim. Generic `sps.*` attributes are candidate locators for
the unary scanner or future sidecar binding; IR self-annotation is never policy
authority.

## One readable snapshot per fixture

Every case lives at `fixtures/<family>/<case>/` and contains exactly one MLIR
file plus one `snapshot.yaml`. A source-annotated case also owns one primary C
file, `policy.sps.yaml`, and `abi.sps.yaml` in that same directory; a case may
add a sibling support translation unit when the compiler boundary requires it.
An expected-`Counterexample` case additionally owns exactly one fixed-name
`counterexample-pair.yaml`; `Proved` and `Unknown` cases must not have one.
Cases with cross-host external-call locators may own a nonclaimable
`contracts.sps.yaml` authoring sidecar, which is not a canonical SPS contract
table.
No source or sidecar may be shared with another case. Snapshot V3 states the
expected final judgment and the sparse endpoint properties that matter to the
fixture; lit separately owns how those endpoints are produced:

```yaml
format_id: SPS-Harness-Fixture-Snapshot-v3
entry: dynamic_kv_length_bad

c_evidence:
  - fixtures/dynamic-kv-length/bad/dynamic_kv_length_bad.c

secret:
  - {arg: 0, name: secret_length}

public:
  - {memory_at_arg: 2, name: public_allocation_count}
  - {memory_at_arg: 3, name: public_iteration_count}

expect:
  final:
    model:
      status: Counterexample
      bad_state: public-counts-mismatch
    deployment: Open
    policy: Complete
    events:
      - kind: Output
        field: valueBytes
        id: public-counts
        first_bad: true
    because: secret_length is stored into both public count fields
  pipelines:
    modeled-shape:
      kind: mlir
      properties:
        operation.names:
          contains: [llvm.store]
```

The `format_id` literal keeps this fixture record disjoint from every SPS-owned
wire interface. Argument numbers are stable references; names are checked display aids. Public
items may also identify a public argument or one of the closed observations
`address`, `allocation-size`, `control`, `release-identity`, `return`, `timing`,
and `transfer`. `allowed` adds a minimal release or audience rule only when needed.
There is no scalar verdict, execution field, test path, capability list, input
graph, endpoint-adapter wrapper, or report-materialization state. Every
snapshot has one `expect.final`: 32 fixtures expect `Proved`, 30 expect
`Counterexample`, and 12 expect `Unknown`; all explicitly expect deployment
`Open` and policy `Complete`. A `Counterexample` names its bad-state class and
one selected event field as `first_bad`. `Proved` and `Counterexample` cases
select at least one closed SPS event field; selectors never contain event
payloads or full traces. The thirteen existing candidates add only
`reference: candidate/expected-report.json`, which is authenticated through the
sibling manifest and checked for agreement with the final axes.

## Mutation coverage without a mutation schema

Mutation is tested through focused semantic twins, not through a universal
snapshot block. Scalar-slot mutation is covered by
`precision-control/overwritten-slot` and
`precision-control/missing-overwrite-bad`; fixed-offset array mutation is
covered by `precision-control/offset-disjoint` and
`precision-control/offset-overlap-bad`; pointer rebinding is covered by the
three `pointer-rebinding` cases below.

| Pointer case | Decisive property | Expected result |
| --- | --- | --- |
| `disjoint-select-bad` | A secret-selected scalar load changes `Memory.allocationClass` even when both bytes and the private output are equal. | `Counterexample(address-trace-mismatch)` |
| `same-allocation-control` | The same pointer-select/load/store shape selects roots in one allocation class, so that allocation-class mismatch is absent. | `Proved` expectation; candidate `AuditAll` is `UNSAT` |
| `pointer-spill-unsupported` | A pointer-valued ordinary store and load survive in the checked artifact. | `Unknown(UnsupportedType)` before relational construction |

Policy owns coalition visibility and secrecy, ABI owns the complete root
partition and metadata, the snapshot owns only the expected axes and decisive
event, and the bad case's synthetic pair owns equal-byte isolation inputs. The
focused consistency contract derives their agreement across those files; it
does not duplicate the facts into Snapshot V3.

## Synthetic counterexample pairs

The snapshot owns the human security oracle; it does not own concrete input
values. Every one of the 30 expected-`Counterexample` fixtures therefore keeps
one public synthetic pair beside it:

```yaml
format_id: SPS-Harness-Synthetic-Counterexample-Pair-v1
claim_boundary: NonClaimableFixtureOracle
source_class: SyntheticTestData
entry: xor_secret_output_bad
coalition:
- observer
inputs:
  low_equal: {}
  high_left:
    secret:
      bitvector: {width: 32, hex: "00000000"}
  high_right:
    secret:
      bitvector: {width: 32, hex: "00000001"}
expected:
  bad_state: public-output-mismatch
  first_difference:
    kind: Output
    field: valueBytes
    id: return
```

The input maps are keyed by policy component ID. They exactly partition the
entry-state components into coalition-visible `low_equal` values and
coalition-hidden values for the two lanes. Scalars use full ABI-width,
fixed-width lowercase hexadecimal bitvectors; initialized root inputs use an
exact byte length and two lowercase hexadecimal digits per byte. At least one
High component differs. The expected bad state and earliest semantic event
must exactly match the snapshot's sole `first_bad` selector.

This file is a fixture input, not a solver model, trace, exact replay witness,
or public receipt. It contains no topology, admission predicate, derived event
sequence, backend result, `ProductSafe`, or `ModelStatus`. Four precision bad
reductions additionally bind the pair's raw SHA-256 in relation binding v2 and
independently replay it; even there, the witness-free reference result stores
neither the pair values nor a normative disposition.

The inventory scans lit `RUN` and `REQUIRES` lines to derive ownership and
capability gates. Each declared pipeline has exactly one RUN binding and each
participating test has one finalizer. Those operational facts intentionally do
not appear in snapshot YAML.

`c/check_harness.py snapshots` validates strict YAML, the one-to-one
MLIR/snapshot layout, function arguments, pointer observations, boundary
equality for `bad`/`fixed` and `*-bad`/`*-fixed` pairs, pipeline lineage and lit
bindings, and the absence of authoritative result claims. It rejects aliases,
anchors, explicit tags, merge keys, duplicate keys, path escapes, and unknown
fields.

### Cross-host authoring locators

An optional `contracts.sps.yaml` makes a cross-host call explicit without
pretending to materialize `ContractTableV2`. Its closed
`SPS-Harness-Authoring-Contracts-v1` rows bind a stable contract ID to one
direct external scalar call ordinal, the entry source host, one distinct
destination host, an integer-only signature, empty memory effects, Unit choice,
total/deterministic intent, and `SPS-ContractWire-v2`. Every row must retain the
limitations `NoFunctionSemantics` and `NotCanonicalContractTableV2`.

The source-boundary resolver checks those locators against the C declaration
and call, includes their endpoint hosts in policy-host coverage, and emits
`ContractLocatorsResolved`. It also always emits `OpenModelObligations`: the
sidecar contains no canonical contract function semantics and cannot discharge
a model gate. Cross-host fixtures therefore use scalar contract calls rather
than pretending that an entry on one host may directly load or store an ABI
root owned by another host.

## Lit checkpoint convention

Producer commands remain visible in lit while the shared runner inspects their
declared endpoints:

```mlir
// RUN: %checkpoint-runner run --snapshot fixtures/dynamic-kv-length/bad/snapshot.yaml --pipeline modeled-shape --endpoint %t.mlir --records %t.checkpoints -- %mlir-opt %s -o %t.mlir
// RUN: %checkpoint-runner finalize --test %s --records %t.checkpoints
```

`PassedV1` and a successful `finalize` mean that the declared checkpoint
evidence matched. They do not mean that the program is secure. `expect.final`
is the fixture's confident expected end-to-end result, while an actual result
can come only from canonical bitcode plus SPS inputs through the conformant
verifier and aggregation path into `SPSRunReportV2`. A future
`check-final --snapshot ... --report ...` command compares that authenticated
report with the same compact final block. No snapshot migration is required.

The checked artifact path and literal producer command remain in lit. A bytes
pipeline names only its manifest digest binding; `check-existing` receives the
artifact through `--endpoint`. The shared source-boundary dispatcher remains a
batched lit producer for source, policy, and ABI validation. Capability gates
are ordinary lit `REQUIRES` features.

Matchers capture only the sparse typed facts needed for the decisive property,
not SSA numbers or whole-module text. Nineteen canonicalization-sensitive
fixtures declare separate raw and canonicalized endpoints. FileCheck remains
only for a documented property outside the typed fact registry.

There are no `--verify-diagnostics` oracles here. The current scanner has its
own feature-gated tests under `../diagnostic/`; future exact model checks belong
under `../sps/` and must consume conformance bundles rather than MLIR text.

`PREFLIGHT FINDING` and `PREFLIGHT CONTROL` blocks are comments checked for
shape and adjacency. Their `preflight expectation` is a prototype review aid,
not a Rev4 diagnostic disposition or run-report result.

## Authority boundary

MLIR is convenient for authoring and reviewing a seed, but Rev4 analyzes frozen
canonical LLVM bitcode. Thirteen selected cases also contain a local `candidate/`
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

Those candidates remain quarantined by the `candidate/` boundary. Their exact
bytes pipelines protect the current thirteen captures, and a compact `reference`
authenticates each existing expected-run sidecar without copying its query,
replay, receipt, or audit machinery into Snapshot V3. The other 61 fixtures
state the same final axes directly without manufacturing candidate artifacts.
A future conformance `artifact.bc` must be deliberately frozen and accompanied
by canonical SPS inputs and an actual run report. The expected final block is
never treated as the actual report. Every counterexample expectation names a
`bad_state` and remains nonclaimable until authenticated restricted evidence
establishes that class.

The current vendored `DeploymentStatusV2` union contains only `Open`; it has no
`Closed` constructor. Accordingly, no present expectation or actual can be
classified `EndToEndClosed` without a future upstream SPS interface revision.

The runner writes observations only below
`LIT_BUILD_ROOT/checkpoints/<case>/<pipeline>.actual.yaml`. It never edits a
snapshot or tracked candidate file.

## Relation-reference precision pairs

Exactly eight cases under `precision-control/` add a
`relation-reference` pipeline. Each case owns two authored files beside its C,
MLIR, policy, ABI, and snapshot:

```text
relation-reference/
  fixture.json   # finite SPS executable-reference program and expected queries
  binding.json   # hashes plus full-program-to-reduction correspondence
```

The snapshot names only stable semantic projections: admission is nonempty,
each High component can vary, the reduced terminal-output surface has no
counterexample, AuditAll is `sat` or `unsat`, and the required backends agree.
Repeated PONF, lowering, digest, solver, and replay requirements live in the
shared `SPS-Reference-Relation-v1` profile rather than being copied into every
snapshot.

For the four expected-bad precision cases, binding v2 also raw-digest-binds
the fixed sibling counterexample pair. The reference validator rematerializes
the reduced values without truncation, checks admission and Low equality, and
independently reproduces the earliest declared difference. The four safe
bindings carry an explicit `counterexamplePair: null`.

The binding records the full 32-bit arguments and roots next to their 1–2-bit
finite counterparts and explicitly says `ExecutableReferenceOnly`,
`HandAuthoredReduction`, `NotFrozenLLVM`, and `ReducedBitWidth`. The generated
result is witness-free and digest-bound. It cannot contain or imply
`ModelStatus`, `ProductSafe`, `NFConforms`, a normative disposition, or a proof
about the readable MLIR. The three evidence layers remain:

```text
snapshot + MLIR intent
  -> executable finite relation-reference evidence
  -> future exact SPS over frozen canonical bitcode
```

See [the Rev4 workflow](REV4_PREFLIGHT_WORKFLOW.md) for that transition.
