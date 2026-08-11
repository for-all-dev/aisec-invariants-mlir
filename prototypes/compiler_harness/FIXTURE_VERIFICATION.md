# Verifying fixture expectations

This guide describes the small, test-only verifier used by the compiler
harness. Its job is to answer one question:

> Did an independently executed fixture produce the test outcome and pipeline
> facts declared in its `snapshot.yaml`?

The verifier does **not** implement SPS normal-form construction, the two-lane
product, PONF, SMT lowering, solver validation, exact replay, policy review, or
deployment closure. Those operations remain the responsibility of their
producers. The verifier only validates their expectation-blind trace, derives a
test position, and compares that actual position with the fixture expectation.

Consequently, every result is permanently bounded as follows:

```text
authority: TestOnly
sensitivity: SyntheticTestData | Restricted
claimable: false
sps_model_status: NotComputed
```

A passing fixture is useful regression evidence. It is not an SPS theorem and
must not be represented as `SPSRunReport`, `ModelStatus`, or `NFConforms`.

## The four contracts

The schemas live in [`contracts/schemas`](contracts/schemas):

| Contract | Owner | Purpose |
| --- | --- | --- |
| `SPS-Harness-Fixture-Snapshot` | Fixture author | The one authoritative expected test position and expected pipeline facts. |
| `SPS-Harness-Trace-Fragment` | A pipeline or decision producer | One expectation-blind record from an actual run. |
| `SPS-Harness-Verification-Trace` | Trace assembler | The complete, deterministic set of actual captures and decision evidence. |
| `SPS-Harness-Verification-Result` | C fixture verifier | The comparison, field-consumption ledger, and any issues. |

All four are closed schemas: unknown fields are rejected. YAML inputs use the
JSON data model only. Parsers must additionally reject duplicate keys, aliases,
anchors, merge keys, explicit tags, nulls, floating-point values, invalid
UTF-8, embedded NULs, surrogate code points, and inputs above their configured
size limits.

The reusable API is declared by the
[`fixture_verifier.h`](include/sps_harness/fixture_verifier.h) C header. C++17
callers may use the ownership-only
[`fixture_verifier.hpp`](include/sps_harness/fixture_verifier.hpp) view. The
[`sps-fixture-verify` host CLI](verifier/src/cli.c), built with
`make -C verifier all`, is a thin file/exit-code adapter over the same two-phase
C API; it does not add derivation rules.

### Snapshot authority

The snapshot owns expectations, not program meaning. Policy and ABI sidecars
remain authoritative for the confidentiality boundary, representation, alias
topology, and public/secret classification. The snapshot records only the
expected consequence of running the bound test:

```yaml
format: SPS-Harness-Fixture-Snapshot
case: loop-bounds/secret-trip-count-bad
entry: bound_secret_trip_count_bad
expect:
  position:
    tag: Counterexample
    cause: world-control-location-mismatch
    first_difference:
      kind: BranchSuccessor
      field: successor
  deployment: Open
  policy: Complete
  events:
    - kind: BranchSuccessor
      field: successor
  pipelines:
    modeled-shape:
      kind: mlir
      properties:
        operation.names:
          ordered: [llvm.icmp, llvm.cond_br]
because: secret counts zero and one choose different first loop successors
```

Every scalar or matcher below `expect` must be checked exactly once. `because`
is required teaching prose. It is recorded as `ExplanationOnly`, but changing
it cannot change derivation, matching, or the process exit status.

### Expectation-blind evidence

No capture command, producer, fragment assembler, or trace-derivation function
may receive a snapshot path or snapshot bytes. In particular, a producer must
emit its complete extractor facts; it must not emit only the facts mentioned in
`expect`, precompute matcher results, or copy an expected status into its
output.

A capture fragment has this shape:

```yaml
format: SPS-Harness-Trace-Fragment
session: loop-bounds-run-001
case: loop-bounds/secret-trip-count-bad
entry: bound_secret_trip_count_bad
record:
  tag: PipelineCapture
  pipeline: modeled-shape
  capture:
    state: Captured
    kind: mlir
    extractor: mlir-structure
    endpoint_sha256: 0000000000000000000000000000000000000000000000000000000000000000
    facts:
      operation.names: [llvm.icmp, llvm.cond_br, llvm.return]
```

The other fragment tags are:

- `RequiredChecks`: actual event coverage and whether every required gate was
  closed;
- `ValidatedCounterexample`: the cause and earliest difference returned by an
  independent replay validator, together with pair, replay, and validator-build
  digests;
- `Blocker`: one actual proof-completion, replay-invalidating, or
  run-finalization blocker;
- `FinalAxes`: the independently produced deployment and policy-review axes.

The assembler requires one or more distinct `PipelineCapture` records, exactly
one `RequiredChecks`, exactly one `FinalAxes`, at most one
`ValidatedCounterexample`, and no duplicate blockers. Every fragment must bind
the same session, case, and entry. It sorts captures and blockers
deterministically and emits one `SPS-Harness-Verification-Trace`.

## Verification algorithm

The order is part of the security boundary. Derivation must finish before the
verifier is allowed to parse the snapshot.

### 1. Run every producer

Run the fixture's existing C/MLIR/compiler/reference checks. Each producer
writes one or more trace fragments containing actual facts or an explicit
failure state. A failed producer is not silently omitted.

For a counterexample case, a hand-authored left/right pair is only an input to
the replay producer. The pair cannot declare itself valid. The producer must:

1. load the pair and all bound policy, ABI, artifact, and configuration data;
2. reconstruct the reduced two-lane product and its relevant checks;
3. run its search or solver;
4. independently replay the returned assignment;
5. derive the earliest unequal modeled observation; and
6. emit `ValidatedCounterexample` only after that replay succeeds.

SAT alone is candidate evidence. Pair-pinned SMT is diagnostic. Only the
independent replay result may populate the validated-counterexample record.

### 2. Assemble one complete trace

Assemble fragments without opening `snapshot.yaml`:

```sh
python3 tools/fixture_trace.py assemble \
  --sensitivity SyntheticTestData \
  --output build/loop-bounds.trace.yaml \
  build/fragments/*.yaml
```

Sensitivity is fail-closed: omitting `--sensitivity` selects `Restricted`,
which also requires an explicit protected output file. Checked-in public test
data must opt into `SyntheticTestData` deliberately.

Assembly fails on mixed identities, duplicate records, missing required
records, forbidden expectation keys, malformed captures, or unsupported
values. The resulting trace still has no expected position and no matcher
results.

### 3. Parse and validate the trace in C

The C verifier reads the trace bytes once and checks the closed trace schema,
identifier domains, event kind/field pairs, capture uniqueness, digests, and
decision consistency. It does not receive snapshot bytes during this phase.

Invalid combinations include:

- a validated counterexample plus a `ReplayInvalidating` blocker;
- any `RunFinalization` blocker in a fixture result;
- `all_required_gates_closed: true` plus any blocker;
- a failed, blocked, unsupported, missing, duplicate, or wrong-kind required
  pipeline capture; and
- no counterexample, no blocker, and gates that are not closed.

These are `Invalid`, not `Unknown`. `Unknown` is a derived test position backed
by an explicit model blocker, not a fallback for missing evidence or a broken
test run.

### 4. Derive the actual test position

With a valid trace, derive exactly one position:

| Actual decision evidence | Derived position |
| --- | --- |
| Validated counterexample and no replay-invalidating/finalization blocker | `Counterexample(cause, first_difference)` |
| No validated counterexample and exactly one proof-completion blocker | `Unknown(blocker.reason)` |
| No validated counterexample and several proof-completion blockers | `Unknown(OpenModelObligations)` |
| No counterexample, no blocker, and all required gates closed | `Proved` |
| Anything else | `Invalid` |

A validated counterexample may coexist with a proof-completion blocker because
the exact replay already exhibits a bad admitted execution. It may not coexist
with a blocker that invalidates that replay.

### 5. Parse the snapshot

Only after Step 4 returns an immutable actual outcome may the verifier parse
`snapshot.yaml`. It validates the closed snapshot schema and confirms that its
case and entry equal the trace identity.

This ordering gives a simple independence test: changing only `expect` must not
change the derived actual outcome or trace digest. It may change only the final
comparison and consumption rows.

### 6. Compare every expectation

The verifier consumes every `expect` leaf exactly once:

1. compare the position tag and the tag-specific cause, first difference, or
   reason;
2. compare deployment and policy axes;
3. compare the complete expected event-coverage set;
4. require exactly one capture for every expected pipeline;
5. require each capture kind to match its pipeline kind;
6. compare byte pipelines by the captured endpoint SHA-256;
7. apply every structured-property matcher; and
8. reject any unknown or unconsumed expectation field.

Matcher meanings are deliberately small:

| Matcher | Meaning |
| --- | --- |
| `equals: X` | The actual typed fact equals `X`. |
| `contains: [X, ...]` | Every listed value occurs in the actual collection. |
| `excludes: [X, ...]` | No listed value occurs in the actual collection. |
| `ordered: [X, ...]` | The values occur as an ordered subsequence. |
| `count: {eq: N}` | Collection size equals `N`. |
| `count: {min: N}` | Collection size is at least `N`. |
| `count: {max: N}` | Collection size is at most `N`. |

Each comparison creates a consumption-ledger row naming the expectation path,
actual path, check, expected value, actual value, and disposition. This ledger
makes a falsely green result caused by a forgotten expectation field visible
and machine-checkable.

Ledger values use only booleans, signed 64-bit integers, strings, lists, and
maps. Null and floating-point values are forbidden. An observed value is tagged
as `{"state":"Present","value":...}`; when an expected fact has no actual
value, it is `{"state":"Missing"}`. The wrapper never overloads JSON null or
reserves a value from the extractor's fact domain.

### 7. Emit the result

The verifier emits one closed `SPS-Harness-Verification-Result`:

```json
{
  "format": "SPS-Harness-Verification-Result",
  "authority": "TestOnly",
  "sensitivity": "SyntheticTestData",
  "claimable": false,
  "sps_model_status": "NotComputed",
  "outcome": {
    "tag": "Matched",
    "case": "loop-bounds/secret-trip-count-bad",
    "entry": "bound_secret_trip_count_bad",
    "actual": {
      "position": {
        "tag": "Counterexample",
        "cause": "world-control-location-mismatch",
        "first_difference": {
          "kind": "BranchSuccessor",
          "field": "successor"
        }
      },
      "deployment": "Open",
      "policy": "Complete"
    }
  },
  "pipelines": [],
  "consumed": [],
  "ignored": [{"path": "/because", "reason": "ExplanationOnly"}],
  "issues": []
}
```

Exit status `0` means `Matched`, `1` means a valid but mismatched expectation,
and `2` means malformed input, inconsistent evidence, a usage error, or an
operational failure.

For a checked-in fixture whose synthetic provenance was verified outside the
trace, the public invocation is:

```sh
verifier/build/sps-fixture-verify \
  --trace TRACE \
  --snapshot SNAPSHOT \
  --allow-synthetic-test-data
```

The result repeats the trace sensitivity rather than silently dropping it. If
trace parsing fails before sensitivity can be authenticated, the result uses
the fail-closed value `Restricted`. Detailed counterexample fields are
appropriate only for checked-in synthetic fixtures. A trace or result marked
`Restricted` must remain in an internal evidence path; do not check it in or
publish its model values, pair, replay, or first-bad coordinates. The host CLI
therefore refuses to serialize a detailed `Restricted` result to standard
output; an in-process caller must route it to an approved restricted store.
The CLI also refuses a self-declared `SyntheticTestData` trace unless its
caller supplies the separate `--allow-synthetic-test-data` assertion. The
in-band trace field is preserved for result classification, but it is never by
itself authorization to release detailed output.

## Worked loop-bound positions

The three loop-bound fixtures form one useful review unit because they exercise
all three derivation arms without changing the result authority.

### Counterexample: secret trip count

Fixture: `fixtures/loop-bounds/secret-trip-count-bad`

The left input uses secret count `0`; the right input uses secret count `1`.
All Low inputs and representation choices are equal. The first loop condition
therefore chooses the exit successor on one lane and the body successor on the
other. `BranchSuccessor.successor` is earlier than any later
`LoopContinuation` observation.

The decision part of the actual trace is:

The repeated hexadecimal values below are illustrative schema-valid digests;
an actual producer must emit the SHA-256 values of its real pair, replay, and
validator build.

```yaml
decision:
  event_coverage:
    - kind: BranchSuccessor
      field: successor
  counterexample:
    tag: Validated
    cause: world-control-location-mismatch
    first_difference:
      kind: BranchSuccessor
      field: successor
    pair_sha256: "1111111111111111111111111111111111111111111111111111111111111111"
    replay_sha256: "2222222222222222222222222222222222222222222222222222222222222222"
    validator:
      id: relation-reference-runner
      build_sha256: "3333333333333333333333333333333333333333333333333333333333333333"
  blockers: []
  all_required_gates_closed: false
  deployment: Open
  policy: Complete
```

The C verifier derives `Counterexample` before it sees the snapshot, then
checks that the snapshot expects the same cause and earliest difference.

### Proved test position: adequate public bound

Fixture: `fixtures/loop-bounds/public-bound-adequate-proved`

The public count is Low and the declared bound covers every admitted loop
execution. The actual producer closes all required test gates, reports the
modeled event surface, and has neither a counterexample nor a blocker:

```yaml
decision:
  event_coverage:
    - kind: LoopContinuation
      field: continueOrExit
    - kind: Output
      field: valueBytes
  counterexample:
    tag: None
  blockers: []
  all_required_gates_closed: true
  deployment: Open
  policy: Complete
```

The derived fixture position is `Proved`. Its meaning is only “this complete
test trace closed the gates defined by this harness fixture.” The result still
says `sps_model_status: NotComputed` because the C verifier did not run the SPS
proof.

The snapshot comparison for this arm is simply:

```yaml
expect:
  position:
    tag: Proved
  # deployment, policy, events, and pipelines follow
```

### Unknown test position: exhausted public bound

Fixture: `fixtures/loop-bounds/public-bound-exhausted-unknown`

The public count is Low, so this is not itself a secret-dependent control
counterexample. However, the configured proof bound can be exhausted while an
admitted execution remains. The bound producer emits an explicit
proof-completion blocker:

```yaml
decision:
  event_coverage: []
  counterexample:
    tag: None
  blockers:
    - scope: ProofCompletion
      reason: LoopRemainder
      source: bound-audit
  all_required_gates_closed: false
  deployment: Open
  policy: Complete
```

The derived position is `Unknown(LoopRemainder)`. If the producer merely
crashed or omitted its decision record, the result would instead be `Invalid`.

The snapshot names the same explicit reason:

```yaml
expect:
  position:
    tag: Unknown
    reason: LoopRemainder
  # deployment, policy, events, and pipelines follow
```

## Review checklist

For each fixture, verify all of the following:

- [ ] Policy and ABI sidecars, not names or comments, define the actual
  confidentiality boundary and representation.
- [ ] Producers run without access to snapshot expectations.
- [ ] Every expected pipeline has one complete actual capture.
- [ ] Capture digests bind the endpoint bytes that the extractor inspected.
- [ ] Failed producers are represented explicitly and cannot disappear.
- [ ] A `Counterexample` comes from independently validated replay, not from an
  authored pair or SAT assignment alone.
- [ ] The earliest difference uses the modeled event order and correct
  kind/field pair.
- [ ] `Unknown` has an explicit proof-completion reason.
- [ ] `Proved` has closed gates, nonempty relevant coverage, no blocker, and no
  validated counterexample.
- [ ] Every leaf below `expect` appears exactly once in the consumption ledger.
- [ ] Editing `because` cannot change the result.
- [ ] Editing only `expect` cannot change trace derivation.
- [ ] The final report remains `TestOnly`, `claimable: false`, and
  `sps_model_status: NotComputed`.
